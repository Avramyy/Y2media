#!/usr/bin/env python3
"""
YouTube Downloader Telegram Bot
Download YouTube videos as MP3 or MP4 directly in Telegram.
"""

import os
import re
import uuid
import time
import logging
import tempfile
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters,
)

# ============ CONFIGURATION ============
# Set your bot token here or via environment variable
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
MAX_FILE_SIZE = 50 * 1024 * 1024  # Telegram limit: 50MB for bots

# ============ LOGGING ============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Temp directory for downloads
DOWNLOAD_DIR = tempfile.mkdtemp(prefix="ytbot_")


def is_youtube_url(url):
    """Check if URL is a valid YouTube link."""
    patterns = [
        r'(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(https?://)?(www\.)?youtu\.be/[\w-]+',
        r'(https?://)?(m\.)?youtube\.com/watch\?v=[\w-]+',
    ]
    return any(re.search(p, url) for p in patterns)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message."""
    await update.message.reply_text(
        "🎬 *YouTube Downloader Bot*\n\n"
        "Send me a YouTube link and I'll download it for you!\n\n"
        "You can choose:\n"
        "• 🎵 MP3 (audio only)\n"
        "• 🎬 MP4 (video)\n\n"
        "Supported qualities:\n"
        "MP3: 128 / 192 / 256 / 320 kbps\n"
        "MP4: 360p / 480p / 720p / 1080p / Best",
        parse_mode="Markdown",
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message."""
    await update.message.reply_text(
        "How to use:\n\n"
        "1. Send a YouTube URL\n"
        "2. Choose format (MP3 or MP4)\n"
        "3. Choose quality\n"
        "4. Wait for download\n"
        "5. Receive your file!\n\n"
        "Commands:\n"
        "/start - Welcome message\n"
        "/help - This message",
    )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle YouTube URL — show video info and format options."""
    url = update.message.text.strip()

    if not is_youtube_url(url):
        await update.message.reply_text(
            "❌ This is not a YouTube link.\n\n"
            "Send a valid YouTube URL like:\n"
            "`https://youtube.com/watch?v=...`\n"
            "`https://youtu.be/...`",
            parse_mode="Markdown",
        )
        return

    # Show loading message
    loading_msg = await update.message.reply_text("⏳ Fetching video info...")

    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            await loading_msg.edit_text("❌ Could not fetch video info.")
            return

        # Format duration
        duration = info.get("duration", 0)
        dur_str = ""
        if duration:
            m, s = divmod(int(duration), 60)
            h, m = divmod(m, 60)
            dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

        title = info.get("title", "Unknown")
        channel = info.get("channel", info.get("uploader", "Unknown"))
        thumbnail = info.get("thumbnail")

        # Store URL in context
        context.user_data["url"] = url
        context.user_data["title"] = title

        # Build response with thumbnail
        caption = (
            f"🎬 *{title[:80]}*\n"
            f"📺 {channel}\n"
            f"⏱️ {dur_str}\n\n"
            f"Choose format and quality:"
        )

        # Format selection keyboard
        keyboard = [
            [
                InlineKeyboardButton("🎵 MP3", callback_data="fmt_mp3"),
                InlineKeyboardButton("🎬 MP4", callback_data="fmt_mp4"),
            ]
        ]

        if thumbnail:
            await loading_msg.delete()
            await update.message.reply_photo(
                photo=thumbnail,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await loading_msg.edit_text(
                caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

    except yt_dlp.utils.DownloadError:
        await loading_msg.edit_text(
            "❌ This video is unavailable or restricted."
        )
    except Exception as e:
        logger.error("Error fetching info: %s", e)
        await loading_msg.edit_text("❌ Something went wrong. Try another video.")


async def format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle format selection (MP3/MP4) — show quality options."""
    query = update.callback_query
    await query.answer()

    fmt = query.data.replace("fmt_", "")  # "mp3" or "mp4"
    context.user_data["format"] = fmt

    if fmt == "mp3":
        keyboard = [
            [
                InlineKeyboardButton("320 kbps ⭐", callback_data="q_320"),
                InlineKeyboardButton("256 kbps", callback_data="q_256"),
            ],
            [
                InlineKeyboardButton("192 kbps", callback_data="q_192"),
                InlineKeyboardButton("128 kbps", callback_data="q_128"),
            ],
        ]
        text = "🎵 *MP3 Audio* — Choose quality:"
    else:
        keyboard = [
            [
                InlineKeyboardButton("Best", callback_data="q_best"),
                InlineKeyboardButton("1080p", callback_data="q_1080"),
            ],
            [
                InlineKeyboardButton("720p", callback_data="q_720"),
                InlineKeyboardButton("480p", callback_data="q_480"),
            ],
            [
                InlineKeyboardButton("360p", callback_data="q_360"),
            ],
        ]
        text = "🎬 *MP4 Video* — Choose quality:"

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quality selection — start download."""
    query = update.callback_query
    await query.answer()

    quality = query.data.replace("q_", "")  # "320", "1080", etc.
    url = context.user_data.get("url")
    fmt = context.user_data.get("format", "mp4")
    title = context.user_data.get("title", "video")

    if not url:
        await query.edit_message_text("❌ Session expired. Send the URL again.")
        return

    await query.edit_message_reply_markup(reply_markup=None)
    status_msg = await query.message.reply_text(
        f"⬇️ Downloading...\n\n"
        f"🎵 Format: {fmt.upper()}\n"
        f"📊 Quality: {quality}\n"
        f"📝 {title[:50]}...",
    )

    try:
        unique = uuid.uuid4().hex[:8]
        output_template = os.path.join(DOWNLOAD_DIR, f"{unique}_%(title)s.%(ext)s")

        if fmt == "mp3":
            opts = {
                "format": "bestaudio/best",
                "outtmpl": output_template,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": quality,
                }],
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
            }
            ext = "mp3"
        else:
            h = quality
            if h == "best":
                fmt_str = "bestvideo+bestaudio/best"
            else:
                fmt_str = (
                    f"bestvideo[height<={h}]+bestaudio"
                    f"/bestvideo[height<={h}]+bestaudio[ext=m4a]"
                    f"/best[height<={h}]/best"
                )
            opts = {
                "format": fmt_str,
                "merge_output_format": "mp4",
                "outtmpl": output_template,
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
            }
            ext = "mp4"

        # Progress callback
        last_update = [0]

        def progress_hook(d):
            if d["status"] == "downloading":
                now = time.time()
                if now - last_update[0] < 3:  # Update every 3 seconds max
                    return
                last_update[0] = now

                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                if total > 0:
                    pct = int(downloaded / total * 100)
                    speed = d.get("speed")
                    speed_str = ""
                    if speed:
                        if speed > 1024 * 1024:
                            speed_str = f" | {speed / 1024 / 1024:.1f} MB/s"
                        else:
                            speed_str = f" | {speed / 1024:.0f} KB/s"
                    try:
                        status_msg.edit_text(
                            f"⬇️ Downloading... {pct}%{speed_str}\n\n"
                            f"{'█' * (pct // 5)}{'░' * (20 - pct // 5)}"
                        )
                    except Exception:
                        pass

        opts["progress_hooks"] = [progress_hook]

        # Download
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # Find the file
        actual_file = None
        for fname in os.listdir(DOWNLOAD_DIR):
            if fname.startswith(unique):
                actual_file = os.path.join(DOWNLOAD_DIR, fname)
                break

        if not actual_file or not os.path.exists(actual_file):
            await status_msg.edit_text("❌ Download failed. Try another video.")
            return

        file_size = os.path.getsize(actual_file)

        if file_size > MAX_FILE_SIZE:
            await status_msg.edit_text(
                f"❌ File too large ({file_size / 1024 / 1024:.1f} MB).\n"
                f"Telegram bot limit is 50MB.\n\n"
                f"Try a lower quality or shorter video."
            )
            os.remove(actual_file)
            return

        # Sanitize filename
        safe_title = "".join(c if c.isalnum() or c in " _-" else "" for c in title)[:50]
        final_name = f"{safe_title}.{ext}"

        await status_msg.edit_text("📤 Uploading to Telegram...")

        # Send file
        with open(actual_file, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=final_name,
                caption=(
                    f"✅ *{title[:80]}*\n\n"
                    f"🎵 Format: {fmt.upper()}\n"
                    f"📊 Quality: {quality}\n"
                    f"📦 Size: {file_size / 1024 / 1024:.1f} MB"
                ),
                parse_mode="Markdown",
            )

        await status_msg.delete()

        # Cleanup
        os.remove(actual_file)

    except yt_dlp.utils.DownloadError as e:
        msg = re.sub(r'\x1b\[[0-9;]*m', '', str(e))
        if "not available" in msg.lower():
            msg = "This video is restricted by YouTube."
        else:
            msg = "Download failed. Try another video."
        await status_msg.edit_text(f"❌ {msg}")
    except Exception as e:
        logger.error("Download error: %s", e)
        await status_msg.edit_text("❌ Something went wrong. Try another video.")


def main():
    """Start the bot."""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("\n========================================")
        print("  YouTube Downloader Telegram Bot")
        print("========================================")
        print("\n  You need a Bot Token first!")
        print("\n  Steps:")
        print("  1. Open Telegram, search @BotFather")
        print("  2. Send /newbot")
        print("  3. Name it (e.g. 'YouTube Downloader Bot')")
        print("  4. Username must end with 'bot'")
        print("  5. Copy the token")
        print("\n  Then either:")
        print("  a) Edit bot.py and paste your token")
        print("  b) Set environment variable:")
        print("     set TELEGRAM_BOT_TOKEN=your_token")
        print("     python bot.py")
        print("========================================\n")
        return

    print("\nYouTube Downloader Bot is starting...")
    print("   Press Ctrl+C to stop.\n")

    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(format_callback, pattern=r"^fmt_"))
    app.add_handler(CallbackQueryHandler(quality_callback, pattern=r"^q_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
