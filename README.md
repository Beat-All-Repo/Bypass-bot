# TW4ALL Bypasser

Cloudflare-tolerant multi-host bypasser and Telegram bot.

## What it handles

- Shorteners (~90 domains in `registry.SHORTENERS`) via a generic engine:
  meta refresh, JS location, base64 `?url=` decode, form submit with token, and
  ajax `/links/go` POSTs. Chains up to 6 hops.
- File hosts: hubcloud / gdflix / filepress / worker gateways (token + `action=direct`),
  Google Drive and usercontent, pixeldrain, gofile, akirabox, vikingfile,
  transfer.it, fuckingfast, MEGA.
- Sites: toonworld4all and the archive (`__PROPS__` parsing), plus a generic
  anchor scan for olamovies / hdhub4u / moviesmod / 4khdhub / vegamovies /
  skymovieshd / katdrama / mkvdrama / pahe and friends.

## Guarantee

`full_episode` iterates **every** source and **every** file. Each file ends as
either a list of final links or an explicit per-file error — it never aborts
the episode, and dead ids are re-minted `RETRIES` times before failing.

## Install

    pip install -r requirements.txt

## CLI

    python -m tw4all.cli "demon slayer season 1" --ep 1
    python -m tw4all.cli "demon slayer season 1" --ep 1 --q 1080p
    python -m tw4all.cli "https://toonworld4all.me/episode/x-1x1" --url --all

## Bot

    export TG_TOKEN=123456:ABC...
    python -m tw4all.bot

## Tuning

`RETRIES`, `MAX_DEPTH`, `DELAY_MIN/MAX`, `FLARE_URL`, `PROXY`, `COOKIE_FILE`.
`HOST_MIRRORS` is where you add a live mirror when a family starts 404ing.