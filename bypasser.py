"""Orchestrator: search → episodes → every source → every final link."""
import logging
from urllib.parse import urljoin, urlsplit

import config
from cf import Fetcher, NotFound
from registry import classify
from shorteners import is_short, solve
from hosts import resolve_host
from sites import search as _search, get_post, get_episode, get_redirect, norm_quality

LOG = logging.getLogger("bypasser")


class Result:
    def __init__(self, ok, links=None, host_url=None, error=None):
        self.ok = ok
        self.links = links or []
        self.host_url = host_url
        self.error = error

    def __repr__(self):
        return "<Result ok=%s links=%d>" % (self.ok, len(self.links))


def search(query, f=None):
    return _search(f or Fetcher(), query)


def episodes(post_url, f=None):
    return get_post(f or Fetcher(), post_url)


def sources(episode_url, f=None):
    return get_episode(f or Fetcher(), episode_url)


def _shortcut(props):
    domain, hidden = props.get("domain"), props.get("hidden")
    if not domain:
        return None
    if hidden and not hidden.startswith("http") and "mega" not in domain:
        return "https://%s/%s" % (domain, hidden.lstrip("/"))
    return domain if domain.startswith("http") else "https://" + domain


def resolve(url, f=None, depth=0, seen=None):
    """Walk any URL to final links. Never raises."""
    f = f or Fetcher()
    seen = seen if seen is not None else set()
    if depth > config.MAX_DEPTH:
        return Result(False, error="depth limit")
    if url in seen:
        return Result(False, error="loop")
    seen.add(url)

    kind = classify(url)
    if kind == "video":
        return Result(True, [url], url)
    if kind in ("host", "direct"):
        try:
            return Result(True, resolve_host(url, f), url)
        except Exception as exc:
            return Result(False, error=str(exc), host_url=url)
    if kind == "short":
        target = solve(f, url)
        if target == url or is_short(target):
            return Result(False, error="shortener did not resolve", host_url=url)
        return resolve(target, f, depth + 1, seen)
    if kind == "site":
        try:
            info = get_episode(f, url)
        except Exception as exc:
            return Result(False, error=str(exc), host_url=url)
        links = []
        for src in info["sources"]:
            for fl in src["files"]:
                sub = resolve(fl["redirect"], f, depth + 1, seen)
                links.extend(sub.links)
        if not links:
            return Result(False, error="no links on page", host_url=url)
        return Result(True, links, url)
    return Result(True, [url], url)


def resolve_file(redirect_url, f=None, retries=None):
    """Resolve one archive file entry, re-minting the redirect id on 404."""
    f = f or Fetcher()
    retries = config.RETRIES if retries is None else retries
    error = None
    for attempt in range(retries):
        try:
            props = get_redirect(f, redirect_url)
        except Exception as exc:
            error = str(exc)
            continue
        target = _shortcut(props) or props.get("destination")
        if not target:
            error = "no target"
            continue
        if is_short(target):
            target = solve(f, target)
        res = resolve(target, f, 1, set())
        if res.ok and res.links:
            return res
        error = res.error
        LOG.info("attempt %s failed on %s: %s", attempt + 1, redirect_url, error)
    return Result(False, error=error, host_url=None)


def full_episode(episode_url, f=None, only_quality=None, on_progress=None):
    """Resolve every file of every source. Always returns a complete tree."""
    f = f or Fetcher()
    info = sources(episode_url, f)
    total = sum(len(s["files"]) for s in info["sources"])
    done = 0
    for src in info["sources"]:
        if only_quality and src["resolution"] != norm_quality(only_quality):
            continue
        for fl in src["files"]:
            res = resolve_file(fl["redirect"], f)
            fl["ok"] = res.ok
            fl["links"] = res.links
            fl["error"] = res.error
            fl["host_url"] = res.host_url
            done += 1
            if on_progress:
                on_progress(done, total, fl)
    return info


def bypass_link(url, f=None):
    """Bypass a pasted link of any supported kind."""
    return resolve(url, f)