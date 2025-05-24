# Aka Compress Bot

A Telegram bot to compress audio/video files before sending them back.

## Features
- Compress audio to 64kbps MP3
- Compress video using H.264 + AAC
- Forced channel join support
- Custom "via @BotUsername" in captions

## Commands
- `/start` - Welcome message
- `/help` - Show help
- `/setchannels` - Set forced join channels (owner only)
- `/setvia` - Set via bot username (owner only)

## Deployment (Render/Koyeb)
- Python service
- Set env vars:
  - `BOT_TOKEN`
  - `BOT_OWNER_ID`
- Build command: `pip install -r requirements.txt`
- Start command: `python main.py`

## Requirements
- Python 3.9+
- `ffmpeg` installed in environment
