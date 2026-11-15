"""Generic multi-strategy shortener engine plus per-family handlers."""
import base64
import json
import logging
import re
from urllib.parse import unquote, urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup

import registry

LOG = logging.getLogger("short")

URL_RE = re.compile(r"https?://[^\s\"'<>()]+")
B64_RE = re.compile(r"[?&](?:url|r|u|id)=([A-Za-z0-9+/=_\-]{16,})")

SHORT_SPECIAL = {
    "ouo.io": ("/go/{id}", "ouo"),
    "ouo.press": ("/go/{id}", "ouo"),
    "shrinkme": ("/links/go", "json"),
    "gplinks": ("/links/go", "json"),
    "oii.la": ("/links/go", "json"),
    "cuty.io": ("/links/go", "json"),
    "cuttlinks.com": ("/links/go", "json"),
    "cuttty.com": ("/links/go", "json"),
    "tpi.li": ("/links/go", "json"),
    "vplink": ("/links/go", "json"),
    "vshort": ("/links/go", "json"),
    "xpshort": ("/links/go", "json"),
    "vipshort": ("/links/go", "json"),
    "shortxlinks": ("/links/go", "json"),
    "earnlinks.in": ("/links/go", "json"),
    "linkpays.in": ("/links/go", "json"),
    "indiaearnx": ("/links/go", "json"),
    "publicearn": ("/links/go", "json"),
    "just2earn.com": ("/links/go", "json"),
    "short4cash.com": ("/links/go", "json"),
    "nowshort": ("/links/go", "json"),
    "mdiskshort": ("/links/go", "json"),
    "inshorturl.in": ("/links/go", "json"),
    "get2short": ("/links/go", "json"),
    "linkshortify": ("/links/go", "json"),
    "lksfy": ("/links/go", "json"),
    "adrinolinks": ("/links/go", "json"),
    "arolinks": ("/links/go", "json"),
    "droplink.co": ("/links/go", "json"),
    "babylinks": ("/links/go", "json"),
    "hblinks": ("/links/go", "json"),
    "fxlinks": ("/links/go", "json"),
    "linkjust.com": ("/links/go", "json"),
    "v2links": ("/links/go", "json"),
    "papajiurl": ("/links/go", "json"),
    "liteshort.com": ("/links/go", "json"),
    "softurl": ("/links/go", "json"),
    "2short.club": ("/links/go", "json"),
}

FALLBACK_ENDPOINTS = ("/links/go", "/go", "/api/go", "/api/links/go")


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


STRATEGIES = (_meta_refresh, _js_redirect, _param_decode)


def _ids(html):
    out = {}
    for name in ("_token", "token", "id", "link_id"):
        m = re.search(r'name=["\']%s["\']\s+value=["\']([^"\']+)' % name, html or "")
        if m:
            out[name] = m.group(1)
    m = re.search(r'data-(?:id|link-id|token)=["\']([^"\']+)', html or "")
    if m:
        out.setdefault("id", m.group(1))
    return out


def _special(f, url, html):
    parts = urlsplit(url)
    host = parts.netloc.lower()
    spec = next((v for k, v in SHORT_SPECIAL.items() if k in host), None)
    if not spec:
        return None
    path_tpl, mode = spec
    fields = _ids(html)
    ident = fields.get("id") or parts.path.strip("/").split("/")[-1]
    if not ident:
        return None
    path = path_tpl.format(id=ident)
    endpoints = [path] if mode == "ouo" else [path] + list(FALLBACK_ENDPOINTS)
    payload = {"id": ident}
    for key in ("_token", "token"):
        if fields.get(key):
            payload[key] = fields[key]
            payload.setdefault("_token", fields[key])
    for endpoint in dict.fromkeys(endpoints):
        try:
            r = f.post("%s://%s%s" % (parts.scheme, parts.netloc, endpoint), data=payload,
                       headers={"referer": url, "x-requested-with": "XMLHttpRequest"})
        except Exception:
            continue
        body = (r.text or "").strip()
        if body.startswith("{"):
            try:
                data = json.loads(body)
            except Exception:
                data = {}
            for key in ("url", "link", "destination", "result"):
                if isinstance(data.get(key), str) and data[key].startswith("http"):
                    return data[key]
        found = _candidates(body)
        if found:
            return found[0]
    return None


def _form_post(f, url, html):
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
            r = f.get(action + "?" + urlencode(fields), headers={"referer": url})
    except Exception:
        return None
    return _meta_refresh(r.text) or _js_redirect(r.text) or _param_decode(r.text)


def solve(f, url, depth=0):
    """Walk a shortener to a non-shortener target. Returns the last reachable URL."""
    current = url
    for _ in range(8):
        try:
            r = f.get(current)
        except Exception as exc:
            LOG.info("hop failed on %s: %s", current, exc)
            return current
        html = r.text or ""
        nxt = _special(f, current, html)
        if not nxt:
            for strategy in STRATEGIES:
                nxt = strategy(html)
                if nxt:
                    break
        if not nxt:
            nxt = _form_post(f, current, html)
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
