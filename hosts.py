"""File host resolvers that return real download URLs, not gateway pages."""
import json
import logging
import re
from urllib.parse import urlsplit, urlunsplit, parse_qs

import config
from cf import NotFound, post_json, post_multipart

LOG = logging.getLogger("hosts")
LINK_RE = re.compile(r"https?://[^\s\"'<>()]+")
KEY_RE = re.compile(r'name=["\'](?:key|keys|id|_token)["\']\s+value=["\']([^"\']+)')
DRIVE_ID = re.compile(r"(?:/file/d/|id=)([A-Za-z0-9_\-]{20,})")


class HostError(Exception):
    pass


def _links(text):
    """Harvest http links from text, excluding self-references."""
    seen = set()
    out = []
    for m in LINK_RE.findall(text or ""):
        link = m.rstrip(".,;)\\\"]")
        if link in seen or not link.startswith("http"):
            continue
        if any(x in link for x in ("hubcloud", "filepress", "appdrive", "gdflix")):
            continue
        seen.add(link)
        out.append(link)
    return out


def _variants(url, family):
    """Rotate mirrors."""
    p = urlsplit(url)
    hosts = [p.netloc] + [h for h in config.HOST_MIRRORS.get(family, []) if h != p.netloc]
    return [urlunsplit((p.scheme, h, p.path, p.query, "")) for h in hosts]


def _get_any(f, urls, referer=None):
    for url in urls:
        try:
            return f.get(url, referer=referer), url
        except NotFound:
            continue
    raise NotFound("all mirrors 404")


def _extract_key(html):
    """Find the hidden key/token needed for the Generate POST."""
    m = KEY_RE.search(html)
    if m:
        return m.group(1)
    # data-key attribute
    m = re.search(r'data-key=["\']([^"\']+)', html)
    if m:
        return m.group(1)
    # input name=id
    m = re.search(r'<input[^>]+name=["\']id["\'][^>]+value=["\']([^"\']+)', html)
    if m:
        return m.group(1)
    return None


def hubcloud(url, f, referer=None):
    """HubCloud: POST action=direct with key, harvest worker or gdrive link."""
    urls = _variants(url, "hubcloud")
    page, used = _get_any(f, urls, referer)
    body = page.text
    key = _extract_key(body)
    LOG.debug("hubcloud key: %s", key)

    # Try the standard generate endpoint
    if key:
        try:
            r = post_multipart(used, {"action": "direct", "key": key}, referer=referer or used)
            body += "\n" + r.text
        except Exception as e:
            LOG.debug("hubcloud direct post failed: %s", e)

        # Some mirrors use ajax.php
        try:
            ajax = "%s://%s/ajax.php?ajax=download" % (urlsplit(used).scheme, urlsplit(used).netloc)
            r = post_json(ajax, {"id": key}, referer=referer or used)
            body += "\n" + r.text
        except Exception as e:
            LOG.debug("hubcloud ajax failed: %s", e)

    # Look for worker links (the real download)
    workers = [l for l in _links(body) if "worker" in l or "googleusercontent" in l]
    gdrive = [l for l in _links(body) if "drive.google.com" in l or "drive.usercontent" in l]
    if workers:
        return workers[:3]
    if gdrive:
        return gdrive[:3]

    # Fallback: if page has a video stream url
    vid = re.search(r'https?://[^\s"\']+\.mp4', body)
    if vid:
        return [vid.group(0)]

    raise HostError("hubcloud: no final link (key=%s)" % key)


def filepress(url, f, referer=None):
    """FilePress: POST /api/file or /api/file/publicDownload, get url field."""
    p = urlsplit(url)
    file_id = p.path.rstrip("/").split("/")[-1]
    if not file_id:
        raise HostError("filepress: no id in url")

    # Try multiple endpoint patterns
    endpoints = [
        "/api/file",
        "/api/file/publicDownload",
        "/api/file/download",
    ]

    for host in [p.netloc] + [h for h in config.HOST_MIRRORS.get("filepress", []) if h != p.netloc]:
        base = "%s://%s" % (p.scheme, host)
        for ep in endpoints:
            try:
                r = post_json(base + ep, {"id": file_id, "publicDownload": True}, referer=referer or url)
                data = r.json()
                LOG.debug("filepress response: %s", data)
                # Extract url from various response shapes
                for key in ("url", "downloadUrl", "link", "data", "file"):
                    val = data.get(key) if isinstance(data, dict) else None
                    if isinstance(val, str) and val.startswith("http"):
                        return [val]
                    if isinstance(val, dict):
                        for sub in ("url", "download", "link"):
                            if val.get(sub):
                                return [val[sub]]
            except Exception as e:
                LOG.debug("filepress %s%s failed: %s", host, ep, e)
                continue

    raise HostError("filepress: all api endpoints failed")


def appdrive(url, f, referer=None):
    """AppDrive: similar to gdflix, POST action=direct."""
    urls = _variants(url, "gdflix")  # appdrive behaves like gdflix family
    page, used = _get_any(f, urls, referer)
    body = page.text
    key = _extract_key(body)

    if key:
        try:
            r = post_multipart(used, {"action": "direct", "key": key}, referer=referer or used)
            body += "\n" + r.text
        except Exception as e:
            LOG.debug("appdrive post failed: %s", e)

    links = _links(body)
    workers = [l for l in links if "worker" in l]
    if workers:
        return workers[:3]
    if links:
        return links[:3]

    raise HostError("appdrive: no final link")


def gdrive(url, f, referer=None):
    ids = DRIVE_ID.findall(url)
    if not ids:
        raise HostError("gdrive: no id")
    fid = ids[0]
    return [
        "https://drive.google.com/uc?export=download&id=" + fid,
        "https://drive.usercontent.google.com/download?id=%s&export=download&confirm=t" % fid
    ]


def mega(url, f, referer=None):
    """MEGA: the url itself is final (needs client-side decryption)."""
    return [url]


def resolve_host(url, f, hint="", referer=None):
    """Route to correct resolver."""
    blob = (url + " " + hint).lower()
    if "hubcloud" in blob:
        return hubcloud(url, f, referer)
    if "filepress" in blob:
        return filepress(url, f, referer)
    if "appdrive" in blob:
        return appdrive(url, f, referer)
    if "drive.google" in blob or "drive.usercontent" in blob:
        return gdrive(url, f, referer)
    if "mega.nz" in blob:
        return mega(url, f, referer)
    # Fallback: try generic link extraction
    try:
        r = f.get(url, referer=referer)
        links = _links(r.text)
        if links:
            return links[:3]
    except Exception:
        pass
    raise HostError("unknown host or no resolver for %s" % url)
