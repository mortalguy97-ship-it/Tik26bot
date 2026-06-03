import logging
import asyncio
import os
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from tracker import TikTokTracker
from database import Database

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHECK_INTERVAL = 60

db = Database()
tracker = TikTokTracker()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *TikTok Auto-Downloader Bot*\n\nI'll monitor TikTok accounts and send you new videos automatically!\n\n📌 *Commands:*\n/watch `@username` — Start watching an account\n/unwatch `@username` — Stop watching an account\n/list — Show all watched accounts\n/status — Bot status\n\nJust send me a TikTok username to get started!",
        parse_mode="Markdown"
    )


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("❗ Please provide a username.\nExample: `/watch @username`", parse_mode="Markdown")
        return
    username = context.args[0].lstrip("@").strip()
    if not username:
        await update.message.reply_text("❗ Invalid username.")
        return
    msg = await update.message.reply_text(f"🔍 Verifying `@{username}`...", parse_mode="Markdown")
    exists = await tracker.verify_account(username)
    if not exists:
        await msg.edit_text(f"❌ Could not find TikTok account `@{username}`. Please check the username.", parse_mode="Markdown")
        return
    added = db.add_watch(chat_id, username)
    if added:
        await msg.edit_text(f"✅ Now watching `@{username}`!\n\nI'll send new videos as soon as they're posted.", parse_mode="Markdown")
    else:
        await msg.edit_text(f"ℹ️ You're already watching `@{username}`.", parse_mode="Markdown")


async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("❗ Please provide a username.\nExample: `/unwatch @username`", parse_mode="Markdown")
        return
    username = context.args[0].lstrip("@").strip()
    removed = db.remove_watch(chat_id, username)
    if removed:
        await update.message.reply_text(f"🗑️ Stopped watching `@{username}`.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❗ You weren't watching `@{username}`.", parse_mode="Markdown")


async def list_watched(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    accounts = db.get_watches(chat_id)
    if not accounts:
        await update.message.reply_text("📭 You're not watching any accounts yet.\nUse `/watch @username` to start!", parse_mode="Markdown")
        return
    lines = "\n".join([f"• `@{a}`" for a in accounts])
    await update.message.reply_text(f"👁️ *Watching {len(accounts)} account(s):*\n\n{lines}", parse_mode="Markdown")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_watches = db.get_total_watches()
    total_chats = db.get_total_chats()
    total_downloaded = db.get_total_downloaded()
    await update.message.reply_text(
        f"📊 *Bot Status*\n\n👥 Active chats: `{total_chats}`\n👁️ Total watches: `{total_watches}`\n📥 Videos sent: `{total_downloaded}`\n⏱️ Check interval: `{CHECK_INTERVAL}s`",
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lstrip("@")
    if text and " " not in text:
        context.args = [text]
        await watch(update, context)
    else:
        await update.message.reply_text("👉 Use `/watch @username` to monitor a TikTok account.", parse_mode="Markdown")


async def check_new_videos(app: Application):
    while True:
        try:
            all_watches = db.get_all_watches()
            for username, chat_ids in all_watches.items():
                try:
                    all_videos = await tracker.get_new_videos(username)
                    new_videos = [(u, vid, d) for u, vid, d in all_videos if not db.is_seen(username, vid)]
                    for video_url, video_id, description in new_videos:
                        video_path = await tracker.download_video(video_url, video_id)
                        if video_path:
                            for chat_id in chat_ids:
                                try:
                                    caption = (f"🎵 *@{username}*\n\n{description[:200] if description else ''}").strip()
                                    with open(video_path, "rb") as vf:
                                        await app.bot.send_video(chat_id=chat_id, video=vf, caption=caption, parse_mode="Markdown")
                                    db.increment_downloaded(chat_id)
                                except Exception as e:
                                    logger.error(f"Failed to send video to {chat_id}: {e}")
                            os.remove(video_path)
                        db.mark_seen(username, video_id)
                except Exception as e:
                    logger.error(f"Error checking @{username}: {e}")
        except Exception as e:
            logger.error(f"Error in check loop: {e}")
        await asyncio.sleep(CHECK_INTERVAL)


async def post_init(app: Application):
    asyncio.create_task(check_new_videos(app))


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("unwatch", unwatch))
    app.add_handler(CommandHandler("list", list_watched))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
