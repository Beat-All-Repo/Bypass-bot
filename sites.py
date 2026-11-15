"""Site scrapers. toonworld4all is full; the rest use the generic anchor scan."""
import json
import re
from urllib.parse import quote, urljoin, urlsplit

from bs4 import BeautifulSoup

import config
from cf import NotFound

EP_RE = re.compile(r"/episode/([a-z0-9\-]+?)-(\d{1,2})x(\d{1,3})/?$")
REDIRECT_RE = re.compile(r"/(?:redirect|links?|goto)/[A-Za-z0-9_\-]+")
SKIP = ("/category/", "/tag/", "/author/", "/page/", "?s=", "/comment-page",
        "/all-movies-list", "/anime-shows-list", "wp-content")


def soup(html):
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def props(html):
    idx = html.find("__PROPS__")
    if idx < 0:
        return None
    start = html.find("{", idx)
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(html[start:])
        return obj
    except ValueError:
        return None


def clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def norm_quality(label):
    low = (label or "").lower()
    for pat, out in config.QUALITY_MAP:
        if re.search(pat, low):
            return out
    return "other"


def search(f, query):
    r = f.get("%s/?s=%s" % (config.BASE, quote(query)))
    doc = soup(r.text)
    out, seen = [], set()
    for art in doc.select("article"):
        a = art.select_one("h2.entry-title a") or art.select_one("h2 a") or art.select_one("a[href]")
        if not a or not a.get("href"):
            continue
        url = a["href"].split("#")[0]
        if url in seen or any(s in url for s in SKIP):
            continue
        seen.add(url)
        thumb = art.select_one("img")
        out.append({"title": clean(a.get_text()), "url": url,
                    "thumb": thumb.get("src") if thumb else None, "date": ""})
    return out


def get_post(f, post_url):
    r = f.get(post_url)
    doc = soup(r.text)
    eps, seen = [], set()
    for a in doc.select('a[href*="/episode/"]'):
        href = a["href"].split("?")[0].rstrip("/")
        m = EP_RE.search(urlsplit(href).path)
        if not m:
            continue
        season, ep = int(m.group(2)), int(m.group(3))
        if (season, ep) in seen:
            continue
        seen.add((season, ep))
        eps.append({"season": season, "episode": ep,
                    "label": "S%02dE%02d" % (season, ep),
                    "url": urljoin(post_url, href)})
    eps.sort(key=lambda e: (e["season"], e["episode"]))
    zip_link = None
    stack = [props(r.text) or {}]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for k in ("zip", "zip_url", "pack"):
                if isinstance(node.get(k), str) and node[k].startswith("http"):
                    zip_link = node[k]
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    title = doc.title.get_text() if doc.title else post_url
    return {"meta": {"title": clean(title), "post": post_url, "zip": zip_link},
            "episodes": eps}


def _walk(node, out):
    if isinstance(node, dict):
        files = node.get("files")
        if isinstance(files, list) and files:
            out.append((node, files))
        for v in node.values():
            _walk(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk(v, out)


def _generic_files(html, base):
    """Fallback for sites without __PROPS__: pull redirects and host links off the page."""
    doc = soup(html)
    items, seen = [], set()
    for a in doc.select("a[href]"):
        href = urljoin(base, a["href"])
        if href in seen:
            continue
        if REDIRECT_RE.search(urlsplit(href).path) or any(
                k in href for k in ("hubcloud", "gdflix", "filepress", "drive.google",
                                    "pixeldrain", "gofile", "mega.nz", "vikingfile",
                                    "akirabox", "transfer.it", "fuckingfast")):
            seen.add(href)
            items.append({"host": clean(a.get_text()) or "link", "short": href, "redirect": href})
    return items


def get_episode(f, episode_url):
    r = f.get(episode_url)
    data = props(r.text)
    sources, seen = [], set()
    if data is not None:
        blocks = []
        _walk(data, blocks)
        for block, files in blocks:
            label = clean(str(block.get("resolution") or block.get("quality") or block.get("size") or ""))
            items = []
            for fl in files:
                if not isinstance(fl, dict):
                    continue
                redirect = fl.get("redirect") or fl.get("link") or fl.get("url")
                if not redirect or redirect in seen:
                    continue
                seen.add(redirect)
                items.append({"host": clean(str(fl.get("host") or "")), "short": redirect,
                              "redirect": urljoin(config.BASE, redirect)})
            if items:
                sources.append({"resolution": norm_quality(label), "label": label,
                                "size": clean(str(block.get("size") or "")), "files": items})
    if not sources:
        items = _generic_files(r.text, episode_url)
        if items:
            sources.append({"resolution": "other", "label": "links", "size": "", "files": items})
    order = {"2160p": 0, "1080p": 1, "720p": 2, "480p": 3, "360p": 4, "other": 5}
    sources.sort(key=lambda s: order.get(s["resolution"], 9))
    doc = soup(r.text)
    return {"url": episode_url, "title": clean(doc.title.get_text() if doc.title else ""),
            "sources": sources}


def get_redirect(f, redirect_url):
    r = f.get(redirect_url)
    data = props(r.text) or {}
    link = data.get("link") or {}
    out = {"destination": data.get("destination") or "",
           "domain": link.get("domain") or data.get("domain") or "",
           "hidden": link.get("hidden") or data.get("hidden") or ""}
    if not out["destination"] and not out["domain"]:
        doc = soup(r.text)
        for a in doc.select("a[href]"):
            href = urljoin(redirect_url, a["href"])
            if any(k in href for k in ("hubcloud", "gdflix", "filepress", "drive.google")):
                out["destination"] = href
                break
    if not out["destination"] and not out["domain"]:
        raise NotFound("empty redirect")
    return out