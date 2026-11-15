"""File host resolvers. Referer is carried through; alternate paths are tried."""
import re
from urllib.parse import urlsplit, urlunsplit

import config
from cf import NotFound, post_json, post_multipart

LINK_RE = re.compile(r"https?://[^\s\"'<>()]+")
DRIVE_ID = re.compile(r"(?:/file/d/|/document/d/|[?&]id=|/uc\?id=)([A-Za-z0-9_\-]{20,})")
KEY_RE = re.compile(r'name=["\'](?:key|keys|id)["\']\s+value=["\']([^"\']+)')
SELF = ("gdflix", "hubcloud", "filepress", "gdlink", "drivehub", "driveseed",
        "nexdrive", "dotflix", "dtflix", "oxxfile", "filebee", "appdrive")


class HostError(Exception):
    pass


def _links(text, exclude_self=True):
    out, seen = [], set()
    for m in LINK_RE.findall(text or ""):
        link = m.rstrip(".,;)\\\"]")
        if link in seen or not link.startswith("http"):
            continue
        if exclude_self and any(s in link for s in SELF):
            continue
        seen.add(link)
        out.append(link)
    return out


def _with_host(url, host):
    p = urlsplit(url)
    return urlunsplit((p.scheme, host, p.path, p.query, ""))


def _variants(url, family):
    p = urlsplit(url)
    hosts = [p.netloc] + [h for h in config.HOST_MIRRORS.get(family, []) if h != p.netloc]
    return [_with_host(url, h) for h in hosts]


def _path_variants(url):
    """HubCloud/FilePress serve the same id under several path prefixes."""
    p = urlsplit(url)
    ident = p.path.rstrip("/").split("/")[-1]
    if not ident:
        return [url]
    out = [url]
    for prefix in ("/drive", "/video", "/file", "/d"):
        cand = urlunsplit((p.scheme, p.netloc, "%s/%s" % (prefix, ident), p.query, ""))
        if cand != url:
            out.append(cand)
    return out


def _get_any(f, urls, referer=None):
    last = None
    for url in urls:
        try:
            return f.get(url, referer=referer), url
        except NotFound as exc:
            last = exc
        except Exception as exc:
            last = exc
    raise NotFound(str(last))


def _drive_direct(file_id):
    return ["https://drive.google.com/uc?export=download&id=" + file_id,
            "https://drive.usercontent.google.com/download?id=%s&export=download&confirm=t" % file_id]


def gdrive_host(url, f, family="gdflix", referer=None):
    """hubcloud / gdflix / filepress / appdrive family: token, POST, harvest."""
    urls = []
    for variant in _variants(url, family):
        urls.extend(_path_variants(variant))
    page, used = _get_any(f, urls, referer)
    body = page.text
    key = None
    m = KEY_RE.search(body) or re.search(r'data-key=["\']([^"\']+)', body)
    if m:
        key = m.group(1)
    if key:
        try:
            body += "\n" + post_multipart(used, {"action": "direct", "key": key},
                                          referer=referer or used).text
        except Exception:
            pass
        try:
            body += "\n" + post_json(used, {"action": "direct", "key": key},
                                     referer=referer or used).text
        except Exception:
            pass
    for endpoint in ("/ajax.php?ajax=download", "/api/file", "/api/file/publicDownload"):
        try:
            body += "\n" + post_json("%s://%s%s" % (urlsplit(used).scheme, urlsplit(used).netloc, endpoint),
                                     {"id": key or "", "publicDownload": True},
                                     referer=referer or used).text
        except Exception:
            pass
    links = _links(body)
    ids = DRIVE_ID.findall(body)
    if ids:
        for did in ids[:2]:
            links = _drive_direct(did) + links
    worker = [l for l in links if "worker" in l or "usercontent" in l]
    rest = [l for l in links if l not in worker]
    final = (worker + rest)[:6]
    if not final:
        raise HostError("no link on %s (id may have rotated)" % urlsplit(used).netloc)
    return final


def hubcloud(url, f, referer=None):
    return gdrive_host(url, f, "hubcloud", referer)


def gdflix(url, f, referer=None):
    return gdrive_host(url, f, "gdflix", referer)


def filepress(url, f, referer=None):
    return gdrive_host(url, f, "filepress", referer)


def appdrive(url, f, referer=None):
    return gdrive_host(url, f, "gdflix", referer)


def gdrive(url, f, referer=None):
    ids = DRIVE_ID.findall(url)
    if not ids:
        raise HostError("no drive id")
    return _drive_direct(ids[0])


def pixeldrain(url, f, referer=None):
    fid = urlsplit(url).path.strip("/").split("/")[-1]
    return ["https://pixeldrain.com/api/file/%s?download" % fid]


def gofile(url, f, referer=None):
    fid = urlsplit(url).path.strip("/").split("/")[-1]
    data = post_json("https://api.gofile.io/contents/%s" % fid, {}, referer=url).json()
    if data.get("status") != "ok":
        raise HostError("gofile: %s" % data.get("status"))
    out = [v["link"] for v in ((data.get("data") or {}).get("children") or {}).values()
           if v.get("link")]
    if not out:
        raise HostError("gofile empty")
    return out


def akirabox(url, f, referer=None):
    page = f.get(url, referer=referer)
    links = _links(page.text)
    if not links:
        raise HostError("akirabox: no link")
    return links[:3]


def vikingfile(url, f, referer=None):
    fid = urlsplit(url).path.strip("/").split("/")[-1]
    for endpoint in ("/api/file/%s" % fid, "/download/%s" % fid):
        try:
            links = _links(f.get(urlsplit(url).scheme + "://" + urlsplit(url).netloc + endpoint,
                                 referer=referer).text)
            if links:
                return links[:3]
        except Exception:
            continue
    raise HostError("vikingfile: no link")


def transfer_it(url, f, referer=None):
    fid = urlsplit(url).path.strip("/").split("/")[-1]
    try:
        data = f.get("https://transfer.it/api/file/%s" % fid, referer=referer).json()
    except Exception:
        data = {}
    for key in ("url", "download", "link"):
        if data.get(key):
            return [data[key]]
    links = _links(f.get(url, referer=referer).text)
    if not links:
        raise HostError("transfer.it: no link")
    return links[:2]


def fuckingfast(url, f, referer=None):
    links = [l for l in _links(f.get(url, referer=referer).text)
             if "fuckingfast" in l or l.endswith(".mkv") or l.endswith(".mp4")]
    if not links:
        raise HostError("fuckingfast: no ddl")
    return links[:2]


def mega(url, f, referer=None):
    hidden = urlsplit(url).path.strip("/").split("/")[-1]
    if len(hidden) > 30:
        return ["https://mega.nz/file/%s#%s" % (hidden[:8], hidden[8:])]
    return ["https://mega.nz/file/%s" % hidden]


def passthrough(url, f, referer=None):
    return [url]


RESOLVERS = {
    "hubcloud": hubcloud, "gdflix": gdflix, "filepress": filepress,
    "appdrive": appdrive, "gdrive": gdrive, "pixeldrain": pixeldrain,
    "gofile": gofile, "akirabox": akirabox, "vikingfile": vikingfile,
    "transfer": transfer_it, "fuckingfast": fuckingfast, "mega": mega,
    "passthrough": passthrough,
}


def pick(url, hint=""):
    blob = (url + " " + hint).lower()
    if "hubcloud" in blob or "hubcdn" in blob or "hubdrive" in blob:
        return "hubcloud"
    if "filepress" in blob or "filebee" in blob:
        return "filepress"
    if "appdrive" in blob or "gdflix" in blob or "gdlink" in blob or "gdshare" in blob \
            or "drivehub" in blob or "driveseed" in blob or "nexdrive" in blob \
            or "oxxfile" in blob or "workers.dev" in blob or "vercel.app" in blob \
            or "onrender.com" in blob or "koyeb.app" in blob or "yolo-school" in blob \
            or "zinkcloud" in blob or "tmbcloud" in blob or "vcloud" in blob \
            or "gcloud.sbs" in blob or "extraflix" in blob or "dotflix" in blob \
            or "dtflix" in blob or "fastdlserver" in blob or "10drives" in blob \
            or "devuploads" in blob or "sportswordz" in blob:
        return "gdflix"
    if "drive.google" in blob or "drive.usercontent" in blob or "olamovies.download" in blob:
        return "gdrive"
    if "pixeldrain" in blob:
        return "pixeldrain"
    if "gofile" in blob:
        return "gofile"
    if "akirabox" in blob:
        return "akirabox"
    if "vikingfile" in blob or "vik1ngfile" in blob:
        return "vikingfile"
    if "transfer.it" in blob:
        return "transfer"
    if "fuckingfast" in blob:
        return "fuckingfast"
    if "mega.nz" in blob or "mega.co.nz" in blob:
        return "mega"
    return "passthrough"


def resolve_host(url, f, hint="", referer=None):
    return RESOLVERS[pick(url, hint)](url, f, referer)
