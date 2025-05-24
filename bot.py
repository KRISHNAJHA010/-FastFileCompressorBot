import os import json import shutil from dotenv import load_dotenv from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv() BOT_TOKEN = os.getenv("BOT_TOKEN") BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))

CONFIG_FILE = "config.json"

def load_config(): if not os.path.exists(CONFIG_FILE): save_config({"channels": [], "via": "@YourBot", "start_message": "Welcome! Send me a file to compress.", "start_image_url": ""}) with open(CONFIG_FILE, "r") as f: return json.load(f)

def save_config(data): with open(CONFIG_FILE, "w") as f: json.dump(data, f, indent=2)

def is_owner(user_id): return user_id == BOT_OWNER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): cfg = load_config() msg = cfg.get("start_message", "Welcome! Send me a file to compress.") img = cfg.get("start_image_url", "") if img: await update.message.reply_photo(photo=img, caption=msg) else: await update.message.reply_text(msg)

async def set_start(update: Update, context: ContextTypes.DEFAULT_TYPE): if not is_owner(update.effective_user.id): return if not context.args: await update.message.reply_text("Usage: /setstart Your welcome message here") return cfg = load_config() cfg["start_message"] = " ".join(context.args) save_config(cfg) await update.message.reply_text("Start message updated.")

async def set_start_image(update: Update, context: ContextTypes.DEFAULT_TYPE): if not is_owner(update.effective_user.id): return if not context.args: await update.message.reply_text("Usage: /setstartimage image_url_or_empty") return cfg = load_config() cfg["start_image_url"] = context.args[0] save_config(cfg) await update.message.reply_text("Start image updated.")

async def set_channels(update: Update, context: ContextTypes.DEFAULT_TYPE): if not is_owner(update.effective_user.id): return if not context.args: await update.message.reply_text("Usage: /setchannels @ch1,@ch2") return channels = context.args[0].split(",") cfg = load_config() cfg["channels"] = channels save_config(cfg) await update.message.reply_text(f"Channels updated to: {', '.join(channels)}")

async def set_via(update: Update, context: ContextTypes.DEFAULT_TYPE): if not is_owner(update.effective_user.id): return if not context.args: await update.message.reply_text("Usage: /setvia @BotUsername") return via = context.args[0] cfg = load_config() cfg["via"] = via save_config(cfg) await update.message.reply_text(f"Via username updated to: {via}")

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool: user_id = update.effective_user.id cfg = load_config() not_joined = [] for channel in cfg.get("channels", []): try: member = await context.bot.get_chat_member(channel.strip(), user_id) if member.status not in ['member', 'administrator', 'creator']: not_joined.append(channel.strip()) except: not_joined.append(channel.strip()) if not_joined: buttons = [[InlineKeyboardButton(f"Join {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in not_joined] await update.message.reply_text("Please join all the required channels to continue:", reply_markup=InlineKeyboardMarkup(buttons)) return False return True

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE): if not await check_join(update, context): return message = update.message media = message.audio or message.video or message.document if not media: await message.reply_text("Please send an audio, video, or document file.") return

file = await media.get_file()
mime = media.mime_type or "application/octet-stream"
input_ext = mime.split('/')[-1]
file_id = media.file_unique_id
file_name = media.file_name or f"{file_id}.{input_ext}"

download_dir = f"downloads/{file_id}"
output_dir = f"compressed/{file_id}"
os.makedirs(download_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

input_path = os.path.join(download_dir, file_name)
await file.download_to_drive(custom_path=input_path)

output_path = os.path.join(output_dir, file_name)
if "audio" in mime:
    output_path = output_path.rsplit('.', 1)[0] + ".mp3"
    os.system(f"ffmpeg -i '{input_path}' -b:a 128k -y '{output_path}'")
elif "video" in mime:
    output_path = output_path.rsplit('.', 1)[0] + ".mp4"
    os.system(f"ffmpeg -i '{input_path}' -vf 'scale=-2:480' -c:v libx264 -crf 28 -preset fast -c:a aac -b:a 128k -y '{output_path}'")
elif file_name.endswith(".zip"):
    shutil.unpack_archive(input_path, download_dir)
    compressed_files = []
    for root, _, files in os.walk(download_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            fext = fname.split('.')[-1].lower()
            comp_out = os.path.join(output_dir, f"compressed_{fname}")
            if fext in ["mp3", "wav", "m4a"]:
                os.system(f"ffmpeg -i '{fpath}' -b:a 128k -y '{comp_out}.mp3'")
                compressed_files.append(f"{comp_out}.mp3")
            elif fext in ["mp4", "mkv", "mov"]:
                os.system(f"ffmpeg -i '{fpath}' -vf 'scale=-2:480' -c:v libx264 -crf 28 -preset fast -c:a aac -b:a 128k -y '{comp_out}.mp4'")
                compressed_files.append(f"{comp_out}.mp4")
    if compressed_files:
        zip_path = f"{output_dir}/compressed_files.zip"
        shutil.make_archive(zip_path.replace(".zip", ""), 'zip', output_dir)
        await message.reply_document(InputFile(zip_path), caption=f"Compressed files via {load_config().get('via', '@YourBot')}")
    shutil.rmtree(download_dir)
    shutil.rmtree(output_dir)
    return
else:
    await message.reply_text("Unsupported file type.")
    return

cfg = load_config()
via = cfg.get("via", "@YourBot")
send_func = message.reply_audio if "audio" in mime else message.reply_video
await send_func(InputFile(output_path), caption=f"via {via}")

shutil.rmtree(download_dir)
shutil.rmtree(output_dir)

if name == "main": app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setchannels", set_channels))
app.add_handler(CommandHandler("setvia", set_via))
app.add_handler(CommandHandler("setstart", set_start))
app.add_handler(CommandHandler("setstartimage", set_start_image))
app.add_handler(MessageHandler(filters.AUDIO | filters.VIDEO | filters.Document.ALL, handle_media))

print("Bot is running...")
app.run_polling()

