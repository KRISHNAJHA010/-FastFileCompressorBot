import os
import zipfile
import shutil
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Directories
DOWNLOAD_DIR = "downloads"
COMPRESS_DIR = "compressed"
START_TEXT_FILE = "start_text.txt"
START_IMAGE_FILE = os.getenv("START_IMAGE", "start.jpg")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(COMPRESS_DIR, exist_ok=True)

# Helpers
def clean_dirs():
    shutil.rmtree(DOWNLOAD_DIR, ignore_errors=True)
    shutil.rmtree(COMPRESS_DIR, ignore_errors=True)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(COMPRESS_DIR, exist_ok=True)

def compress_audio(input_path, output_path, bitrate="128k"):
    os.system(f'ffmpeg -i "{input_path}" -c:a libmp3lame -b:a {bitrate} -y "{output_path}"')

def compress_video(input_path, output_path, resolution="480"):
    scale = {
        "360": "640:360", "480": "854:480",
        "720": "1280:720", "1080": "1920:1080"
    }[resolution]
    os.system(f'ffmpeg -i "{input_path}" -vf "scale={scale}" -preset veryfast -crf 28 -c:v libx264 -c:a aac -b:a 64k -y "{output_path}"')

def load_start_text():
    if os.path.exists(START_TEXT_FILE):
        with open(START_TEXT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "Welcome! Send an MP3/MP4 or ZIP/Folder to compress. Choose options after upload."

def save_start_text(text):
    with open(START_TEXT_FILE, "w", encoding="utf-8") as f:
        f.write(text)

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = load_start_text()
    if os.path.exists(START_IMAGE_FILE):
        await update.message.reply_photo(photo=InputFile(START_IMAGE_FILE), caption=text)
    else:
        await update.message.reply_text(text)

# Command: /setstart
async def set_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        new_text = " ".join(context.args)
        save_start_text(new_text)
        await update.message.reply_text("Start message updated!")
    else:
        await update.message.reply_text("Usage: /setstart Your welcome message")

# Command: /setstartimage
async def set_start_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        await file.download_to_drive(START_IMAGE_FILE)
        await update.message.reply_text("Start image updated!")
    else:
        await update.message.reply_text("Send this command with a photo to update the welcome image.")

# Handle uploads
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clean_dirs()
    doc = update.message.document or update.message.audio or update.message.video
    if not doc:
        await update.message.reply_text("Send an audio, video, or zip file.")
        return

    file = await doc.get_file()
    file_path = os.path.join(DOWNLOAD_DIR, doc.file_name)
    await file.download_to_drive(file_path)

    if file_path.endswith(".zip"):
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(DOWNLOAD_DIR)
        os.remove(file_path)

    context.user_data["input_files"] = []
    for root, _, files in os.walk(DOWNLOAD_DIR):
        for f in files:
            path = os.path.join(root, f)
            if f.lower().endswith((".mp3", ".mp4")):
                context.user_data["input_files"].append(path)

    if not context.user_data["input_files"]:
        await update.message.reply_text("No MP3 or MP4 files found.")
        return

    options = [
        [InlineKeyboardButton("MP3 128kbps", callback_data="audio_128k"),
         InlineKeyboardButton("MP3 64kbps", callback_data="audio_64k")],
        [InlineKeyboardButton("MP4 360p", callback_data="video_360"),
         InlineKeyboardButton("MP4 480p", callback_data="video_480")],
        [InlineKeyboardButton("MP4 720p", callback_data="video_720"),
         InlineKeyboardButton("MP4 1080p", callback_data="video_1080")]
    ]
    await update.message.reply_text("Choose compression quality:", reply_markup=InlineKeyboardMarkup(options))

# Compression handler
async def compress_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data
    files = context.user_data.get("input_files", [])
    out_files = []

    for path in files:
        base = os.path.basename(path)
        out_path = os.path.join(COMPRESS_DIR, base)

        if choice.startswith("audio"):
            bitrate = choice.split("_")[1]
            out_path = out_path.rsplit(".", 1)[0] + ".mp3"
            compress_audio(path, out_path, bitrate)
        elif choice.startswith("video"):
            res = choice.split("_")[1]
            out_path = out_path.rsplit(".", 1)[0] + ".mp4"
            compress_video(path, out_path, res)

        out_files.append(out_path)

    if len(out_files) == 1:
        await query.message.reply_document(InputFile(out_files[0]), caption="Compressed by @YourBotUsername")
    else:
        zip_path = os.path.join(COMPRESS_DIR, "compressed_output.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for f in out_files:
                zipf.write(f, arcname=os.path.basename(f))
        await query.message.reply_document(InputFile(zip_path), caption="Compressed by @YourBotUsername")

    clean_dirs()

# Initialize bot
app = Application.builder().token(BOT_TOKEN).build()

# Command handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setstart", set_start))
app.add_handler(MessageHandler(filters.PHOTO & filters.CaptionRegex("^/setstartimage"), set_start_image))

# File upload handler
app.add_handler(MessageHandler(filters.Document.ALL | filters.AUDIO | filters.VIDEO, handle_file))

# Callback handler for buttons
app.add_handler(CallbackQueryHandler(compress_choice))

# Start polling
app.run_polling()
