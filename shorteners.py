"""Generic multi-strategy shortener engine. Every listed family routes here."""
import base64
import logging
import re
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup

import registry

LOG = logging.getLogger("short")

URL_RE = re.compile(r"https?://[^\s\"'<>()]+")

B64_RE = re.compile(r"[?&](?:url|r|u|id)=([A-Za-z0-9+/=_\-]{16,})")


def is_short(url):
    return registry.classify(url) == "short"


def _clean(link):
    return link.rstrip(".,;)\\\"]")


def _candidates(text):
    out = []
    for m in URL_RE.findall(text or ""):
        link = _clean(m)
        if link not in out:
            out.append(link)
    return out


def _meta_refresh(html):
    m = re.search(r'http-equiv=["\']?refresh["\']?[^>]*url=([^"\'>\s]+)', html or "", re.I)
    return unquote(m.group(1)) if m else None


def _js_redirect(html):
    for pat in (r"window\.location(?:\.href)?\s*=\s*[\"']([^\"']+)",
                r"location\.replace\([\"']([^\"']+)",
                r"location\.assign\([\"']([^\"']+)",
                r"href\s*=\s*[\"'](https?://[^\"']+)[\"']\s*;"):
        m = re.search(pat, html or "")
        if m:
            return m.group(1)
    return None


def _param_decode(html):
    m = B64_RE.search(html or "")
    if not m:
        return None
    raw = unquote(m.group(1))
    if raw.startswith("http"):
        return raw
    for pad in ("", "=", "=="):
        try:
            dec = base64.b64decode(raw + pad, altchars=b"-_").decode("utf-8", "ignore")
        except Exception:
            continue
        if dec.startswith("http"):
            return dec
    return None


def _form_post(f, url, html):
    """Submit the ad page's own form (token fields included) the way a browser would."""
    doc = BeautifulSoup(html, "html.parser")
    form = doc.find("form")
    if not form:
        return None
    action = urljoin(url, form.get("action") or url)
    fields = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if name:
            fields[name] = inp.get("value") or ""
    try:
        if form.get("method", "get").lower() == "post":
            r = f.post(action, data=fields, headers={"referer": url})
        else:
            from urllib.parse import urlencode
            r = f.get(action + "?" + urlencode(fields), headers={"referer": url})
    except Exception:
        return None
    return _meta_refresh(r.text) or _js_redirect(r.text) or _param_decode(r.text)


def _ajax_go(f, url, html):
    """shrinkme / gplinks / oii style: POST <origin>/links/go with the ajax header."""
    parts = urlsplit(url)
    m = re.search(r'name=["\'](_token|token|id)["\']\s+value=["\']([^"\']+)', html or "")
    if not m:
        m = re.search(r"data-(?:id|token)=[\"']([^\"']+)", html or "")
        if not m:
            return None
        payload = {"id": m.group(1)}
    else:
        payload = {m.group(1): m.group(2)}
    payload.setdefault("_token", payload.get("token", ""))
    endpoint = "%s://%s/links/go" % (parts.scheme, parts.netloc)
    try:
        r = f.post(endpoint, data=payload,
                   headers={"referer": url, "x-requested-with": "XMLHttpRequest"})
        body = r.text.strip()
        if body.startswith("{"):
            import json
            try:
                data = json.loads(body)
            except Exception:
                data = {}
            for key in ("url", "link", "destination"):
                if data.get(key):
                    return data[key]
        return _candidates(body)[0] if _candidates(body) else None
    except Exception:
        return None


STRATEGIES = (_meta_refresh, _js_redirect, _param_decode)


def solve(f, url, depth=0):
    """Walk a shortener to a non-shortener target. Returns the last reachable URL."""
    current = url
    for step in range(6):
        try:
            r = f.get(current)
        except Exception as exc:
            LOG.info("short hop failed on %s: %s", current, exc)
            return current
        html = r.text or ""
        nxt = None
        for strategy in STRATEGIES:
            nxt = strategy(html)
            if nxt:
                break
        if not nxt:
            nxt = _form_post(f, current, html) or _ajax_go(f, current, html)
        if not nxt:
            for cand in _candidates(html):
                if not is_short(cand) and "javascript" not in cand:
                    nxt = cand
                    break
        if not nxt:
            return current
        nxt = urljoin(current, nxt)
        if nxt == current:
            return current
        if not is_short(nxt):
            return nxt
        current = nxt
    return current