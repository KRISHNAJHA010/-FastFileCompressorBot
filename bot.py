import os
import time
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
import subprocess

# Logging
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")
BOT_USERNAME = "@FileCompressorBot"

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Send an MP3/MP4 or ZIP/Folder to compress. Choose options after upload.")

# When media is received
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document or update.message.audio or update.message.video
    if not file:
        await update.message.reply_text("Please send an MP3/MP4 file.")
        return

    file_path = f"downloads/{file.file_unique_id}_{file.file_name}"
    os.makedirs("downloads", exist_ok=True)
    await update.message.reply_text("Downloading file...")

    new_file = await context.bot.get_file(file.file_id)
    await new_file.download_to_drive(file_path)

    context.user_data['original_file'] = file_path
    context.user_data['file_type'] = file.mime_type

    keyboard = [
        [InlineKeyboardButton("MP3 128kbps", callback_data="mp3_128"),
         InlineKeyboardButton("MP3 64kbps", callback_data="mp3_64")],
        [InlineKeyboardButton("MP4 360p", callback_data="mp4_360"),
         InlineKeyboardButton("MP4 480p", callback_data="mp4_480")],
        [InlineKeyboardButton("MP4 720p", callback_data="mp4_720"),
         InlineKeyboardButton("MP4 1080p", callback_data="mp4_1080")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose compression quality:", reply_markup=reply_markup)

# Compression + Upload
async def compress_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    input_path = context.user_data.get("original_file")
    mime = context.user_data.get("file_type", "")
    quality = query.data
    output_path = f"compressed/{os.path.basename(input_path)}"
    os.makedirs("compressed", exist_ok=True)

    await query.edit_message_text("Compressing...")

    # FFmpeg command
    if "mp3" in mime or quality.startswith("mp3"):
        bitrate = "128k" if quality == "mp3_128" else "64k"
        output_path = output_path.replace(".mp3", f"_{bitrate}.mp3")
        cmd = ["ffmpeg", "-i", input_path, "-b:a", bitrate, "-y", output_path]
    else:
        scale = {
            "mp4_360": "640:360",
            "mp4_480": "854:480",
            "mp4_720": "1280:720",
            "mp4_1080": "1920:1080"
        }.get(quality, "640:360")
        output_path = output_path.replace(".mp4", f"_{scale.replace(':','x')}.mp4")
        cmd = ["ffmpeg", "-i", input_path, "-vf", f"scale={scale}", "-preset", "ultrafast", "-y", output_path]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    await query.edit_message_text("Uploading...")

    start_time = time.time()
    file_size = os.path.getsize(output_path)
    mime_type = "audio/mpeg" if output_path.endswith(".mp3") else "video/mp4"

    with open(output_path, "rb") as f:
        input_file = InputFile(f, filename=os.path.basename(output_path), mime_type=mime_type)

        if mime_type.startswith("audio"):
            sent_msg = await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=input_file,
                caption="Compressed by " + BOT_USERNAME
            )
        else:
            sent_msg = await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=input_file,
                caption="Compressed by " + BOT_USERNAME
            )

    end_time = time.time()
    duration = end_time - start_time
    speed = (file_size / 1024) / duration

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"Size: {file_size // 1024} KB\nUpload Speed: {speed:.2f} KB/s\nETA: {duration:.2f} sec"
    )

# Run the bot
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.AUDIO | filters.VIDEO, handle_file))
    app.add_handler(CallbackQueryHandler(compress_and_send))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
    
