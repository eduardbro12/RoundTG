import asyncio
import logging
import os
import subprocess
import tempfile

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from groq import Groq

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)


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


def extract_audio(input_path: str, audio_path: str) -> bool:
    command = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        "-f", "mp3",
        audio_path
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode == 0


def transcribe_audio(audio_path: str) -> str:
    with open(audio_path, "rb") as f:
        transcription = groq_client.audio.transcriptions.create(
            file=("audio.mp3", f.read()),
            model="whisper-large-v3",
            language="ru"
        )
    return transcription.text


def summarize_text(text: str) -> str:
    if not text or len(text.strip()) < 10:
        return None

    response = groq_client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {
                "role": "user",
                "content": f"Вот текст из видео. Напиши краткое резюме в 1-2 предложениях о чём говорится. Без вступлений, только суть.\n\nТекст: {text}"
            }
        ],
        max_tokens=200
    )
    return response.choices[0].message.content.strip()


@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Отправь мне видео, и я пришлю:\n"
        "🔵 Кружок\n"
        "📝 Краткое резюме о чём говорится в видео"
    )


@dp.message(F.video | F.document)
async def handle_video(message: Message):
    await message.answer("⏳ Обрабатываю видео, подожди...")

    file_id = message.video.file_id if message.video else message.document.file_id

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.mp4")
            output_path = os.path.join(tmpdir, "output.mp4")
            audio_path = os.path.join(tmpdir, "audio.mp3")

            file = await bot.get_file(file_id)
            await bot.download_file(file.file_path, destination=input_path)

            # Конвертируем в кружок
            if not convert_to_video_note(input_path, output_path):
                await message.answer("❌ Не удалось обработать видео.")
                return

            # Отправляем кружок
            with open(output_path, "rb") as f:
                await message.answer_video_note(
                    video_note=BufferedInputFile(f.read(), filename="circle.mp4"),
                    length=640
                )

            # Извлекаем аудио и транскрибируем
            summary_text = None
            if extract_audio(input_path, audio_path):
                try:
                    transcript = transcribe_audio(audio_path)
                    if transcript and len(transcript.strip()) > 10:
                        summary_text = summarize_text(transcript)
                except Exception as e:
                    logging.error(f"Transcription error: {e}")

            if summary_text:
                await message.answer(f"📝 {summary_text}")
            else:
                await message.answer("🔇 Речь в видео не обнаружена.")

    except Exception as e:
        logging.error(f"Error: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@dp.message()
async def handle_other(message: Message):
    await message.answer("📹 Отправь видео!")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
