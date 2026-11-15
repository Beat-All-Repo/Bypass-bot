"""python -m tw4all.cli "demon slayer season 1" [--ep 1] [--q 1080p] [--all]"""
import argparse
import logging
import sys

from bypasser import search, episodes, full_episode

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def dump(ep, data):
    print("\n%s  %s" % (ep["label"], data["title"]))
    for src in data["sources"]:
        print("  [%s] %s" % (src["resolution"], src["size"]))
        for fl in src["files"]:
            head = "    %-12s %s" % (fl["host"], "OK" if fl.get("ok") else "FAIL")
            print(head)
            for link in fl.get("links") or []:
                print("      -> %s" % link)
            if not fl.get("ok"):
                print("      !! %s" % (fl.get("error") or "unknown"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--ep", type=int)
    ap.add_argument("--q")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--url", action="store_true")
    args = ap.parse_args()

    results = [{"title": args.query, "url": args.query}] if args.url else search(args.query)
    if not results:
        print("no results")
        return 1
    for i, res in enumerate(results[: args.limit], 1):
        print("%d. %s\n   %s" % (i, res["title"], res["url"]))

    for res in results[: args.limit]:
        info = episodes(res["url"])
        print("\n== %s  (%d episodes)" % (info["meta"]["title"], len(info["episodes"])))
        if info["meta"].get("zip"):
            print("zip: %s" % info["meta"]["zip"])
        chosen = info["episodes"]
        if args.ep:
            chosen = [e for e in chosen if e["episode"] == args.ep]
        elif not args.all:
            chosen = chosen[:1]
        for ep in chosen:
            dump(ep, full_episode(ep["url"], only_quality=args.q))
    return 0


if __name__ == "__main__":
    sys.exit(main())