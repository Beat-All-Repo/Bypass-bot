"""Telegram bot. Handles links and searches, shows every source and final link."""
import asyncio
import logging
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

import config
from bypasser import search, episodes, sources, full_episode, bypass_link

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
LOG = logging.getLogger("bot")
STORE = {}


def put(data):
    key = uuid.uuid4().hex[:12]
    STORE[key] = data
    return key


def take(key):
    return STORE.get(key)


def allowed(update):
    if not config.ALLOWED_USERS:
        return True
    user = update.effective_user
    return bool(user and user.id in config.ALLOWED_USERS)


def clip(text, size=52):
    text = " ".join((text or "").split())
    return text if len(text) <= size else text[: size - 1] + "…"


def link_rows(links, tag=""):
    return [[InlineKeyboardButton("%s%d" % (tag, i), url=link)]
            for i, link in enumerate(links[:6], 1)]


async def start(update, ctx):
    if not allowed(update):
        await update.message.reply_text("not authorised")
        return
    await update.message.reply_text("Send an anime name, or paste any link to bypass.\n/help")


async def help_cmd(update, ctx):
    await update.message.reply_text(
        "• name → results → episode → quality → every source resolved\n"
        "• paste a shortener, hubcloud, gdflix, filepress, drive, pixeldrain, gofile, "
        "vikingfile, transfer.it, fuckingfast or archive link to bypass it\n"
        "• MEGA returns a link only, the key stays client side")


async def on_text(update, ctx):
    if not allowed(update):
        await update.message.reply_text("not authorised")
        return
    text = (update.message.text or "").strip()
    if not text:
        return

    if text.startswith("http"):
        msg = await update.message.reply_text("bypassing…")
        res = await asyncio.to_thread(bypass_link, text)
        if not res.ok:
            await msg.edit_text("failed: %s" % res.error)
            return
        await msg.edit_text("\n".join(res.links[:8]),
                            reply_markup=InlineKeyboardMarkup(link_rows(res.links, "open ")),
                            disable_web_page_preview=True)
        return

    msg = await update.message.reply_text("searching…")
    results = await asyncio.to_thread(search, text)
    if not results:
        await msg.edit_text("no results")
        return
    rows = [[InlineKeyboardButton(clip(r["title"]), callback_data="r:" + put({"url": r["url"]}))]
            for r in results[:10]]
    await msg.edit_text("results for <b>%s</b>" % text,
                        reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)


async def on_result(update, ctx):
    q = update.callback_query
    await q.answer()
    item = take(q.data.split(":", 1)[1])
    if not item:
        await q.edit_message_text("expired")
        return
    await q.edit_message_text("loading episodes…")
    info = await asyncio.to_thread(episodes, item["url"])
    rows = [[InlineKeyboardButton(ep["label"],
                                  callback_data="e:" + put({"url": ep["url"], "label": ep["label"]}))]
            for ep in info["episodes"][: config.PAGE_SIZE * 3]]
    if info["meta"].get("zip"):
        rows.append([InlineKeyboardButton("whole season (zip)",
                                          callback_data="e:" + put({"url": info["meta"]["zip"], "label": "ZIP"}))])
    rows.append([InlineKeyboardButton("all episodes", callback_data="a:" + put({"url": item["url"]}))])
    await q.edit_message_text("<b>%s</b>\n%d episodes" % (info["meta"]["title"], len(info["episodes"])),
                              reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)


async def on_episode(update, ctx):
    q = update.callback_query
    await q.answer()
    item = take(q.data.split(":", 1)[1])
    if not item:
        await q.edit_message_text("expired")
        return
    await q.edit_message_text("reading sources…")
    data = await asyncio.to_thread(sources, item["url"])
    rows = [[InlineKeyboardButton("%s  %s" % (s["resolution"], s["size"]),
                                  callback_data="q:" + put({"url": item["url"], "q": s["resolution"]}))]
            for s in data["sources"]]
    if not rows:
        await q.edit_message_text("no sources")
        return
    await q.edit_message_text("<b>%s</b>\nchoose quality" % item["label"],
                              reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)


async def on_quality(update, ctx):
    q = update.callback_query
    await q.answer()
    item = take(q.data.split(":", 1)[1])
    if not item:
        await q.edit_message_text("expired")
        return
    await q.edit_message_text("resolving every source…")
    data = await asyncio.to_thread(full_episode, item["url"], None, item["q"])
    lines, rows = [], []
    for src in data["sources"]:
        if src["resolution"] != item["q"]:
            continue
        lines.append("<b>%s %s</b>" % (src["resolution"], src["size"]))
        for fl in src["files"]:
            if fl.get("ok") and fl["links"]:
                lines.append("• %s" % (fl["host"] or "link"))
                rows.extend(link_rows(fl["links"], (fl["host"] or "link")[:8] + " "))
            else:
                lines.append("• %s — %s" % (fl["host"] or "link", fl.get("error") or "failed"))
    rows.append([InlineKeyboardButton("retry", callback_data="q:" + put(item))])
    body = "\n".join(lines) or "nothing resolved"
    await q.edit_message_text(body[:3800], reply_markup=InlineKeyboardMarkup(rows),
                              parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def on_all(update, ctx):
    q = update.callback_query
    await q.answer()
    item = take(q.data.split(":", 1)[1])
    if not item:
        await q.edit_message_text("expired")
        return
    info = await asyncio.to_thread(episodes, item["url"])
    rows = [[InlineKeyboardButton(ep["label"],
                                  callback_data="e:" + put({"url": ep["url"], "label": ep["label"]}))]
            for ep in info["episodes"]]
    await q.edit_message_text("all episodes", reply_markup=InlineKeyboardMarkup(rows))


def main():
    if not config.TG_TOKEN:
        raise SystemExit("TG_TOKEN not set")
    app = Application.builder().token(config.TG_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CallbackQueryHandler(on_result, pattern=r"^r:"))
    app.add_handler(CallbackQueryHandler(on_episode, pattern=r"^e:"))
    app.add_handler(CallbackQueryHandler(on_quality, pattern=r"^q:"))
    app.add_handler(CallbackQueryHandler(on_all, pattern=r"^a:"))
    LOG.info("polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()