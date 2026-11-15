"""Solve a whole season to final links.

python -m tw4all.crawl --url https://toonworld4all.me/demon-slayer-... --out out/
python -m tw4all.crawl --query "demon slayer season 1" --limit 1 --out out/
"""
import argparse
import json
import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
from cf import Fetcher
from bypasser import search, episodes, sources, resolve_file

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
LOG = logging.getLogger("crawl")
LOCK = threading.Lock()


def cell(fl, res):
    return {"host": fl["host"], "redirect": fl["redirect"], "ok": res.ok,
            "links": res.links, "error": res.error}


def solve_episode(f, ep):
    data = sources(ep["url"], f)
    out = {"label": ep["label"], "title": data["title"], "url": ep["url"], "sources": []}
    for src in data["sources"]:
        block = {"resolution": src["resolution"], "size": src["size"], "files": []}
        for fl in src["files"]:
            res = resolve_file(fl["redirect"], f)
            block["files"].append(cell(fl, res))
            LOG.info("%s %s %s -> %s", ep["label"], src["resolution"],
                     fl["host"] or "?", "ok" if res.ok else res.error)
        out["sources"].append(block)
    return out


def to_markdown(meta, eps):
    lines = ["# %s" % meta["title"], "", "post: %s" % meta["post"], ""]
    if meta.get("zip"):
        lines += ["whole season: %s" % meta["zip"], ""]
    total = ok = 0
    for ep in eps:
        lines.append("## %s — %s" % (ep["label"], ep["title"]))
        lines.append(ep["url"])
        for src in ep["sources"]:
            lines.append("")
            lines.append("**%s %s**" % (src["resolution"], src["size"]))
            for fl in src["files"]:
                total += 1
                if fl["ok"] and fl["links"]:
                    ok += 1
                    for link in fl["links"]:
                        lines.append("- %s: %s" % (fl["host"] or "link", link))
                else:
                    lines.append("- %s: FAILED (%s)" % (fl["host"] or "link",
                                                        fl["error"] or "unknown"))
        lines.append("")
    lines.insert(3, "resolved: %d/%d files" % (ok, total))
    return "\n".join(lines), ok, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--query")
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--out", default="out")
    ap.add_argument("--ep", type=int)
    ap.add_argument("--q")
    args = ap.parse_args()

    if not args.url and not args.query:
        ap.error("need --url or --query")

    os.makedirs(args.out, exist_ok=True)
    f = Fetcher()

    post = args.url
    if not post:
        results = search(args.query, f)
        if not results:
            print("no results")
            return 1
        post = results[0]["url"]
        print("post: %s" % post)

    info = episodes(post, f)
    chosen = info["episodes"]
    if args.ep:
        chosen = [e for e in chosen if e["episode"] == args.ep]
    print("%d episodes, %s" % (len(chosen), info["meta"]["title"]))

    done = []
    with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_JOBS) as pool:
        futures = {pool.submit(solve_episode, f, ep): ep for ep in chosen}
        for fut in as_completed(futures):
            ep = futures[fut]
            try:
                done.append(fut.result())
            except Exception as exc:
                LOG.warning("%s failed: %s", ep["label"], exc)
                done.append({"label": ep["label"], "title": ep["label"],
                             "url": ep["url"], "sources": [], "error": str(exc)})
    done.sort(key=lambda e: e["label"])

    body, ok, total = to_markdown(info["meta"], done)
    stem = os.path.join(args.out, info["meta"]["title"][:60].replace(" ", "-") or "season")
    with open(stem + ".md", "w", encoding="utf-8") as fh:
        fh.write(body)
    with open(stem + ".json", "w", encoding="utf-8") as fh:
        json.dump({"meta": info["meta"], "episodes": done}, fh, indent=2)
    print("resolved %d/%d files -> %s.md" % (ok, total, stem))
    return 0


if __name__ == "__main__":
    sys.exit(main())