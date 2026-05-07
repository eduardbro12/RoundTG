import asyncio
import logging
import os
import subprocess
import tempfile

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


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


@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Отправь мне видео, и я пришлю его обратно в виде кружка 🔵\n\n"
        "⚠️ Ограничения Telegram для кружков:\n"
        "• Максимум 60 секунд\n"
        "• Видео будет обрезано до квадрата"
    )


@dp.message(F.video | F.document)
async def handle_video(message: Message):
    await message.answer("⏳ Обрабатываю видео, подожди...")

    if message.video:
        file_id = message.video.file_id
    else:
        file_id = message.document.file_id

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.mp4")
            output_path = os.path.join(tmpdir, "output.mp4")

            file = await bot.get_file(file_id)
            await bot.download_file(file.file_path, destination=input_path)

            success = convert_to_video_note(input_path, output_path)

            if not success:
                await message.answer("❌ Не удалось обработать видео. Попробуй другой формат.")
                return

            with open(output_path, "rb") as f:
                video_data = f.read()

            await message.answer_video_note(
                video_note=BufferedInputFile(video_data, filename="circle.mp4"),
                length=640
            )

    except Exception as e:
        logging.error(f"Error processing video: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@dp.message()
async def handle_other(message: Message):
    await message.answer("📹 Пожалуйста, отправь видео!")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
