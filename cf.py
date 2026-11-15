"""Cloudflare-tolerant fetch layer with referer propagation."""
import json
import logging
import os
import random
import time
from urllib.parse import urlparse

import config

LOG = logging.getLogger("cf")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

CF_MARKERS = ("Just a moment", "cf-chl", "cf-browser-verification", "Attention Required",
              "checking your browser", "Enable JavaScript and cookies")

try:
    from curl_cffi import requests as cffi
except Exception:
    cffi = None
try:
    import cloudscraper
except Exception:
    cloudscraper = None
try:
    import requests as plain
except Exception:
    plain = None


class Blocked(Exception):
    pass


class NotFound(Exception):
    pass


def _is_challenge(status, body):
    if status in (403, 429, 503):
        return True
    head = (body or "")[:6000]
    return any(m in head for m in CF_MARKERS)


def _sleep():
    time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))


class _Jar:
    def __init__(self, path):
        self.path = path
        self.data = {}
        if path and os.path.exists(path):
            try:
                with open(path) as fh:
                    self.data = json.load(fh)
            except Exception:
                self.data = {}

    def get(self, host):
        return self.data.get(host, {})

    def set(self, host, cookies):
        if not self.path or not cookies:
            return
        self.data[host] = dict(cookies)
        try:
            with open(self.path, "w") as fh:
                json.dump(self.data, fh)
        except Exception:
            pass


class Resp:
    def __init__(self, status, text, url, headers=None):
        self.status_code = status
        self.text = text
        self.content = text.encode("utf-8", "ignore")
        self.url = url
        self.headers = headers or {}

    @property
    def ok(self):
        return 200 <= self.status_code < 400


class Fetcher:
    def __init__(self):
        self.jar = _Jar(config.COOKIE_FILE)
        self._sessions = {}

    def _host(self, url):
        return urlparse(url).netloc

    def _cffi(self, host):
        key = ("cffi", host)
        if key not in self._sessions:
            imp = random.choice(config.IMPERSONATE_POOL)
            try:
                s = cffi.Session(impersonate=imp, timeout=config.TIMEOUT)
            except Exception:
                s = cffi.Session(timeout=config.TIMEOUT)
            s.headers.update({"user-agent": UA, "accept-language": "en-US,en;q=0.9"})
            for k, v in self.jar.get(host).items():
                try:
                    s.cookies.set(k, v, domain=host)
                except Exception:
                    pass
            self._sessions[key] = s
        return self._sessions[key]

    def _cs(self, host):
        key = ("cs", host)
        if key not in self._sessions:
            s = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False})
            s.headers.update({"user-agent": UA, "accept-language": "en-US,en;q=0.9"})
            for k, v in self.jar.get(host).items():
                try:
                    s.cookies.set(k, v, domain=host)
                except Exception:
                    pass
            self._sessions[key] = s
        return self._sessions[key]

    def _flare(self, method, url, headers):
        payload = {"cmd": "request.%s" % method.lower(), "url": url,
                   "maxTimeout": config.TIMEOUT * 1000}
        if headers:
            payload["headers"] = headers
        r = plain.post(config.FLARE_URL + "/v1", json=payload, timeout=config.TIMEOUT + 20)
        sol = r.json().get("solution") or {}
        if not sol.get("response"):
            raise Blocked("flare failed")
        return Resp(sol.get("status", 200), sol["response"], url)

    def request(self, method, url, headers=None, allow_redirects=True, data=None,
                referer=None):
        host = self._host(url)
        hdrs = {
            "user-agent": UA,
            "accept-language": "en-US,en;q=0.9",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "cross-site" if referer else "none",
            "upgrade-insecure-requests": "1",
        }
        if referer:
            hdrs["referer"] = referer
        hdrs.update(headers or {})

        chain = []
        if cffi:
            chain.append("cffi")
        if cloudscraper:
            chain.append("cs")
        if config.FLARE_URL:
            chain.append("flare")
        if not chain:
            raise Blocked("no transport")
        proxies = {"http": config.PROXY, "https": config.PROXY} if config.PROXY else None
        last = None

        for _ in range(config.RETRIES):
            for transport in chain:
                try:
                    if transport == "cffi":
                        s = self._cffi(host)
                        r = s.request(method, url, headers=hdrs, data=data,
                                      allow_redirects=allow_redirects,
                                      timeout=config.TIMEOUT, proxies=proxies)
                        out = Resp(r.status_code, r.text, str(r.url), dict(r.headers))
                        try:
                            self.jar.set(host, dict(s.cookies.items()))
                        except Exception:
                            pass
                    elif transport == "cs":
                        s = self._cs(host)
                        r = s.request(method, url, headers=hdrs, data=data,
                                      allow_redirects=allow_redirects,
                                      timeout=config.TIMEOUT, proxies=proxies)
                        out = Resp(r.status_code, r.text, str(r.url), dict(r.headers))
                    else:
                        out = self._flare(method, url, hdrs)
                    last = out
                    if not _is_challenge(out.status_code, out.text):
                        if out.status_code == 404:
                            raise NotFound(url)
                        _sleep()
                        return out
                    LOG.warning("challenge %s via %s", out.status_code, transport)
                except NotFound:
                    raise
                except Exception as exc:
                    last = exc
                    LOG.debug("transport %s: %s", transport, exc)
            _sleep()
        raise Blocked("blocked: %s (%s)" % (url, last))

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)


def post_multipart(url, fields, referer=None):
    headers = {"user-agent": UA, "referer": referer or url,
               "origin": "https://" + urlparse(url).netloc}
    files = {k: (None, v) for k, v in fields.items()}
    return plain.post(url, files=files, headers=headers,
                      timeout=config.TIMEOUT, allow_redirects=True)


def post_json(url, payload, referer=None):
    headers = {"user-agent": UA, "referer": referer or url,
               "origin": "https://" + urlparse(url).netloc,
               "x-requested-with": "XMLHttpRequest",
               "content-type": "application/json"}
    return plain.post(url, json=payload, headers=headers, timeout=config.TIMEOUT)
