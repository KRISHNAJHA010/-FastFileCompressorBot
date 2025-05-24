import os
import json
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))

if not BOT_TOKEN or BOT_OWNER_ID == 0:
    raise Exception("BOT_TOKEN and BOT_OWNER_ID must be set in the .env file")

CONFIG_FILE = "config.json"
logging.basicConfig(level=logging.INFO)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config({"channels": [], "via": "@YourBot"})
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def is_owner(user_id):
    return user_id == BOT_OWNER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Send me an audio/video to compress. Use /setchannels and /setvia to configure (owner only).")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - Start bot\n"
        "/help - Show help\n"
        "/setchannels - Set forced join channels (owner only)\n"
        "/setvia - Set visible via bot username (owner only)"
    )

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
        except Exception as e:
            logging.warning(f"Join check failed for {channel.strip()}: {e}")
            not_joined.append(channel.strip())
    if not_joined:
        buttons = [[InlineKeyboardButton(f"Join {ch}", url=f"https://t.me/{ch.lstrip('@')}")]
                   for ch in not_joined]
        await update.message.reply_text("Please join all the required channels to continue:",
                                        reply_markup=InlineKeyboardMarkup(buttons))
        return False
    return True

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_join(update, context):
        return
    message = update.message
    media = message.audio or message.video or message.document
    if not media:
        await message.reply_text("Please send an audio, video, or document file.")
        return
    if media.file_size > 100 * 1024 * 1024:
        await message.reply_text("File is too large (max 100MB). Please send a smaller file.")
        return

    await message.reply_text("Compressing your file, please wait...")

    file = await media.get_file()
    mime = media.mime_type or "application/octet-stream"
    input_ext = mime.split('/')[-1]
    file_id = media.file_unique_id
    input_path = f"downloads/{file_id}.{input_ext}"
    output_path = f"compressed/{file_id}.mp3" if "audio" in mime else f"compressed/{file_id}.mp4"

    os.makedirs("downloads", exist_ok=True)
    os.makedirs("compressed", exist_ok=True)
    await file.download_to_drive(custom_path=input_path)

    if "audio" in mime:
        os.system(f"ffmpeg -i '{input_path}' -b:a 64k -y '{output_path}'")
    else:
        os.system(f"ffmpeg -i '{input_path}' -vcodec libx264 -crf 28 -preset veryfast -acodec aac -b:a 64k -y '{output_path}'")

    cfg = load_config()
    via = cfg.get("via", "@YourBot")
    send_func = message.reply_audio if "audio" in mime else message.reply_video
    await send_func(InputFile(output_path), caption=f"via {via}")

    os.remove(input_path)
    os.remove(output_path)

if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("setchannels", set_channels))
    app.add_handler(CommandHandler("setvia", set_via))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VIDEO | filters.Document.ALL, handle_media))
    print("Bot is running...")
    app.run_polling()
