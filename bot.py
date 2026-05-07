import logging
import os
import subprocess
import tempfile

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)


def convert_to_video_note(input_path: str, output_path: str) -> bool:
    command = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", "crop=min(iw\\,ih):min(iw\\,ih),scale=640:640",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-t", "60",
        "-movflags", "+faststart",
        output_path
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode == 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Отправь мне видео, и я пришлю его обратно в виде кружка 🔵\n\n"
        "⚠️ Ограничения Telegram для кружков:\n"
        "• Максимум 60 секунд\n"
        "• Видео будет обрезано до квадрата"
    )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Обрабатываю видео, подожди...")

    if update.message.video:
        file = await update.message.video.get_file()
    else:
        file = await update.message.document.get_file()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.mp4")
            output_path = os.path.join(tmpdir, "output.mp4")

            await file.download_to_drive(input_path)

            success = convert_to_video_note(input_path, output_path)

            if not success:
                await update.message.reply_text("❌ Не удалось обработать видео. Попробуй другой формат.")
                return

            with open(output_path, "rb") as f:
                await update.message.reply_video_note(video_note=f, length=640)

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📹 Пожалуйста, отправь видео!")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.ALL, handle_other))
    app.run_polling()


if __name__ == "__main__":
    main()
