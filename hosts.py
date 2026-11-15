"""File host resolvers. Every one returns a list of final links or raises HostError."""
import json
import re
from urllib.parse import parse_qs, urljoin, urlsplit

import config
from cf import NotFound, post_json, post_multipart
from registry import classify

LINK_RE = re.compile(r"https?://[^\s\"'<>()]+")
DRIVE_ID = re.compile(r"(?:/file/d/|/document/d/|[?&]id=|/uc\?id=)([A-Za-z0-9_\-]{20,})")
KEY_RE = re.compile(r'name=["\'](?:key|keys|id)["\']\s+value=["\']([^"\']+)')
SELF = ("gdflix", "hubcloud", "filepress", "gdlink", "drivehub", "driveseed",
        "nexdrive", "dotflix", "dtflix", "oxxfile", "filebee")


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


def _variants(url, family):
    parts = urlsplit(url)
    hosts = [parts.netloc] + [h for h in config.HOST_MIRRORS.get(family, []) if h != parts.netloc]
    return ["https://%s%s" % (h, parts.path) for h in hosts]


def _get_any(f, urls):
    last = None
    for url in urls:
        try:
            return f.get(url), url
        except NotFound as exc:
            last = exc
    raise NotFound(str(last))


def _drive_direct(file_id):
    return ["https://drive.google.com/uc?export=download&id=" + file_id,
            "https://drive.usercontent.google.com/download?id=%s&export=download&confirm=t" % file_id]


def gdrive_host(url, f, family="gdflix"):
    """hubcloud / gdflix / filepress / worker-gateway family: token then POST action=direct."""
    page, used = _get_any(f, _variants(url, family))
    body = page.text
    key = None
    m = KEY_RE.search(body) or re.search(r'data-key=["\']([^"\']+)', body)
    if m:
        key = m.group(1)
    if key:
        try:
            resp = post_multipart(used, {"action": "direct", "key": key}, referer=used)
            body += "\n" + resp.text
        except Exception:
            pass
    for endpoint in ("/ajax.php?ajax=download", "/api/file", "/api/file/publicDownload"):
        if endpoint in body:
            continue
        try:
            resp = post_json(urljoin(used, endpoint), {"id": key or "", "publicDownload": True},
                             referer=used)
            body += "\n" + resp.text
        except Exception:
            pass
    links = _links(body)
    drive_ids = DRIVE_ID.findall(body)
    if drive_ids:
        for did in drive_ids[:2]:
            links = _drive_direct(did) + links
    worker = [l for l in links if "worker" in l or "usercontent" in l]
    rest = [l for l in links if l not in worker]
    final = (worker + rest)[:6]
    if not final:
        raise HostError("no link on %s" % urlsplit(used).netloc)
    return final


def hubcloud(url, f):
    return gdrive_host(url, f, "hubcloud")


def gdflix(url, f):
    return gdrive_host(url, f, "gdflix")


def filepress(url, f):
    return gdrive_host(url, f, "filepress")


def gdrive(url, f):
    ids = DRIVE_ID.findall(url)
    if not ids:
        raise HostError("no drive id")
    return _drive_direct(ids[0])


def pixeldrain(url, f):
    fid = urlsplit(url).path.strip("/").split("/")[-1]
    return ["https://pixeldrain.com/api/file/%s?download" % fid]


def gofile(url, f):
    fid = urlsplit(url).path.strip("/").split("/")[-1]
    r = post_json("https://api.gofile.io/contents/%s" % fid, {}, referer=url)
    data = r.json()
    if data.get("status") != "ok":
        raise HostError("gofile: %s" % data.get("status"))
    content = (data.get("data") or {}).get("children") or {}
    out = []
    for item in content.values():
        if item.get("link"):
            out.append(item["link"])
    if not out:
        raise HostError("gofile empty")
    return out


def akirabox(url, f):
    page = f.get(url)
    links = _links(page.text)
    if not links:
        raise HostError("akirabox: no link")
    return links[:3]


def vikingfile(url, f):
    fid = urlsplit(url).path.strip("/").split("/")[-1]
    for endpoint in ("/api/file/%s" % fid, "/download/%s" % fid):
        try:
            r = f.get(urljoin(url, endpoint))
            links = _links(r.text)
            if links:
                return links[:3]
        except Exception:
            continue
    raise HostError("vikingfile: no link")


def transfer_it(url, f):
    fid = urlsplit(url).path.strip("/").split("/")[-1]
    r = f.get("https://transfer.it/api/file/%s" % fid)
    try:
        data = r.json()
    except Exception:
        data = {}
    for key in ("url", "download", "link"):
        if data.get(key):
            return [data[key]]
    links = _links(r.text)
    if not links:
        raise HostError("transfer.it: no link")
    return links[:2]


def fuckingfast(url, f):
    r = f.get(url)
    links = [l for l in _links(r.text) if "fuckingfast" in l or l.endswith(".mkv") or l.endswith(".mp4")]
    if not links:
        raise HostError("fuckingfast: no ddl")
    return links[:2]


def mega(url, f):
    hidden = urlsplit(url).path.strip("/").split("/")[-1]
    if len(hidden) > 30:
        return ["https://mega.nz/file/%s#%s" % (hidden[:8], hidden[8:])]
    return ["https://mega.nz/file/%s" % hidden]


def passthrough(url, f):
    return [url]


RESOLVERS = {
    "hubcloud": hubcloud, "gdflix": gdflix, "filepress": filepress,
    "gdrive": gdrive, "pixeldrain": pixeldrain, "gofile": gofile,
    "akirabox": akirabox, "vikingfile": vikingfile, "transfer": transfer_it,
    "fuckingfast": fuckingfast, "mega": mega, "passthrough": passthrough,
}


def pick(url, hint=""):
    blob = (url + " " + hint).lower()
    if "hubcloud" in blob or "hubcdn" in blob or "hubdrive" in blob:
        return "hubcloud"
    if "filepress" in blob or "filebee" in blob:
        return "filepress"
    if "gdflix" in blob or "gdlink" in blob or "gdshare" in blob or "drivehub" in blob \
            or "driveseed" in blob or "nexdrive" in blob or "oxxfile" in blob \
            or "workers.dev" in blob or "vercel.app" in blob or "onrender.com" in blob \
            or "koyeb.app" in blob or "yolo-school" in blob or "zinkcloud" in blob \
            or "tmbcloud" in blob or "vcloud" in blob or "gcloud.sbs" in blob \
            or "extraflix" in blob or "dotflix" in blob or "dtflix" in blob \
            or "fastdlserver" in blob or "10drives" in blob or "devuploads" in blob \
            or "sportswordz" in blob:
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


def resolve_host(url, f, hint=""):
    return RESOLVERS[pick(url, hint)](url, f)