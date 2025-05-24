import os
import json
import shutil
import zipfile
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))

CONFIG_FILE = "config.json"
DOWNLOAD_DIR = "downloads"
COMPRESS_DIR = "compressed"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config({
            "channels": [],
            "via": "@YourBot",
            "start_message": "Welcome! Send me a file or ZIP to compress.",
            "start_image_url": ""
        })
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def is_owner(user_id):
    return user_id == BOT_OWNER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    msg = cfg.get("start_message", "Welcome! Send me a file to compress.")
    img = cfg.get("start_image_url", "")
    if img:
        await update.message.reply_photo(photo=img, caption=msg)
    else:
        await update.message.reply_text(msg)

async def set_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /setstart Your welcome message here")
        return
    cfg = load_config()
    cfg["start_message"] = " ".join(context.args)
    save_config(cfg)
    await update.message.reply_text("Start message updated.")

async def set_start_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /setstartimage image_url_or_empty")
        return
    cfg = load_config()
    cfg["start_image_url"] = context.args[0]
    save_config(cfg)
    await update.message.reply_text("Start image updated.")

async def set_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /setchannels @ch1,@ch2")
        return
    channels = context.args[0].split(",")
    cfg = load_config()
    cfg["channels"] = channels
    save_config(cfg)
    await update.message.reply_text(f"Channels updated to: {', '.join(channels)}")

async def set_via(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /setvia @BotUsername")
        return
    via = context.args[0]
    cfg = load_config()
    cfg["via"] = via
    save_config(cfg)
    await update.message.reply_text(f"Via username updated to: {via}")

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    cfg = load_config()
    not_joined = []
    for channel in cfg.get("channels", []):
        try:
            member = await context.bot.get_chat_member(channel.strip(), user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_joined.append(channel.strip())
        except:
            not_joined.append(channel.strip())
    if not_joined:
        buttons = [[InlineKeyboardButton(f"Join {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in not_joined]
        await update.message.reply_text("Please join all required channels to continue:", reply_markup=InlineKeyboardMarkup(buttons))
        return False
    return True

def compress_audio(input_path, output_path, bitrate="128k"):
    os.system(f"ffmpeg -i '{input_path}' -b:a {bitrate} -y '{output_path}'")

def compress_video(input_path, output_path, resolution="480"):
    scale = {
        "360": "640:360",
        "480": "854:480",
        "720": "1280:720",
        "1080": "1920:1080"
    }.get(resolution, "854:480")
    os.system(f"ffmpeg -i '{input_path}' -vf scale={scale} -crf 28 -preset veryfast -acodec aac -b:a 128k -y '{output_path}'")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_join(update, context):
        return

    message = update.message
    media = message.document or message.video or message.audio
    if not media:
        await message.reply_text("Send an audio/video/document/zip file.")
        return

    file = await media.get_file()
    filename = media.file_name or f"{media.file_unique_id}"
    mime = media.mime_type or "application/octet-stream"
    ext = os.path.splitext(filename)[-1]
    uid = media.file_unique_id
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(COMPRESS_DIR, exist_ok=True)

    input_path = os.path.join(DOWNLOAD_DIR, f"{uid}{ext}")
    await file.download_to_drive(custom_path=input_path)

    cfg = load_config()
    via = cfg.get("via", "@YourBot")

    if ext == ".zip":
        extract_folder = os.path.join(DOWNLOAD_DIR, uid)
        os.makedirs(extract_folder, exist_ok=True)
        with zipfile.ZipFile(input_path, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)
        compressed_files = []
        for root, _, files in os.walk(extract_folder):
            for f in files:
                full_path = os.path.join(root, f)
                name, extension = os.path.splitext(f)
                compressed_path = os.path.join(COMPRESS_DIR, f"compressed_{name}{extension}")
                if extension.lower() in [".mp3", ".wav", ".aac"]:
                    compress_audio(full_path, compressed_path, "128k")
                elif extension.lower() in [".mp4", ".mkv", ".mov"]:
                    compress_video(full_path, compressed_path, "480")
                compressed_files.append(compressed_path)
        zip_output = os.path.join(COMPRESS_DIR, f"compressed_{uid}.zip")
        with zipfile.ZipFile(zip_output, 'w') as zipf:
            for file in compressed_files:
                zipf.write(file, arcname=os.path.basename(file))
        await message.reply_document(InputFile(zip_output), caption=f"via {via}")
        shutil.rmtree(extract_folder)
        os.remove(zip_output)

    elif "audio" in mime:
        out = os.path.join(COMPRESS_DIR, f"{uid}.mp3")
        compress_audio(input_path, out, "128k")
        await message.reply_audio(InputFile(out), caption=f"via {via}")
        os.remove(out)

    elif "video" in mime:
        out = os.path.join(COMPRESS_DIR, f"{uid}.mp4")
        compress_video(input_path, out, "480")
        await message.reply_video(InputFile(out), caption=f"via {via}")
        os.remove(out)

    else:
        await message.reply_text("Unsupported file type.")

    os.remove(input_path)

if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setstart", set_start))
    app.add_handler(CommandHandler("setstartimage", set_start_image))
    app.add_handler(CommandHandler("setchannels", set_channels))
    app.add_handler(CommandHandler("setvia", set_via))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_media))

    print("Bot is running...")
    app.run_polling()
