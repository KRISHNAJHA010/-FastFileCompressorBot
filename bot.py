import os
import zipfile
import shutil
import asyncio
import mimetypes
import subprocess
from pathlib import Path
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

OWNER_ID = 123456789  # Replace with your Telegram ID
BOT_USERNAME = "YourBotUsername"
CHANNEL_USERNAME = "YourChannel"

START_TEXT = "Send a ZIP or folder containing MP3 or MP4 files."
START_IMG_PATH = "start.jpg"

async def set_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    new_msg = " ".join(context.args)
    global START_TEXT
    START_TEXT = new_msg
    await update.message.reply_text("Start message updated.")

async def set_start_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    photo = update.message.photo or []
    if not photo:
        return await update.message.reply_text("Send an image.")
    await update.message.photo[-1].get_file().download_to_drive(START_IMG_PATH)
    await update.message.reply_text("Start image updated.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(START_IMG_PATH):
        await update.message.reply_photo(photo=START_IMG_PATH, caption=START_TEXT)
    else:
        await update.message.reply_text(START_TEXT)

async def handle_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document
    if not file.file_name.endswith(".zip"):
        return await update.message.reply_text("Only ZIP files are supported.")

    msg = await update.message.reply_text("Uploading and processing...")
    download_path = f"downloads/{update.message.message_id}_{file.file_name}"
    os.makedirs(download_path, exist_ok=True)

    zip_file_path = f"{download_path}.zip"
    await file.get_file().download_to_drive(zip_file_path)

    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(download_path)
    except zipfile.BadZipFile:
        return await msg.edit_text("Invalid ZIP file.")

    files = list(Path(download_path).rglob("*"))
    audio_files = [f for f in files if f.suffix.lower() in [".mp3"]]
    video_files = [f for f in files if f.suffix.lower() in [".mp4"]]

    if audio_files and not video_files:
        kb = [[InlineKeyboardButton("64kbps", callback_data=f"compress_audio|64|{download_path}"),
               InlineKeyboardButton("128kbps", callback_data=f"compress_audio|128|{download_path}")]]
    elif video_files and not audio_files:
        kb = [[InlineKeyboardButton("360p", callback_data=f"compress_video|360|{download_path}"),
               InlineKeyboardButton("480p", callback_data=f"compress_video|480|{download_path}"),
               InlineKeyboardButton("720p", callback_data=f"compress_video|720|{download_path}")]]
    else:
        return await msg.edit_text("ZIP must contain only MP3 or only MP4 files.")

    await msg.edit_text("Choose compression quality:", reply_markup=InlineKeyboardMarkup(kb))

async def compress_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, quality, path = query.data.split("|", 2)
    msg = await query.edit_message_text("Compressing files...")

    out_dir = f"compressed/{Path(path).name}_{datetime.now().timestamp()}"
    os.makedirs(out_dir, exist_ok=True)

    if action == "compress_audio":
        for file in Path(path).rglob("*.mp3"):
            out_path = f"{out_dir}/{file.stem}_{quality}kbps.mp3"
            cmd = ["ffmpeg", "-i", str(file), "-b:a", f"{quality}k", out_path, "-y"]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    elif action == "compress_video":
        scale = {
            "360": "640:360",
            "480": "854:480",
            "720": "1280:720"
        }[quality]
        for file in Path(path).rglob("*.mp4"):
            out_path = f"{out_dir}/{file.stem}_{quality}p.mp4"
            cmd = ["ffmpeg", "-i", str(file), "-vf", f"scale={scale}", out_path, "-y"]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    zip_out = shutil.make_archive(out_dir, 'zip', out_dir)
    await query.message.reply_document(document=InputFile(zip_out), caption=f"Compressed by @{BOT_USERNAME}")
    shutil.rmtree(path)
    shutil.rmtree(out_dir)

app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setstart", set_start))
app.add_handler(CommandHandler("setstartimage", set_start_image))
app.add_handler(MessageHandler(filters.Document.ZIP, handle_zip))
app.add_handler(CallbackQueryHandler(compress_callback))

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    app.run_polling()

