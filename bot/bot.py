import logging
import subprocess
import shutil
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import asyncio
from datetime import datetime
from chatgpt_api.gpt import transcribe_audio, evaluate_ielts
from bot.config import BOT_TOKEN, VIDEO_SAVING_PATH

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

FFMPEG = (
    shutil.which("ffmpeg")
    or r"C:\Users\imfya\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe"
)


@dp.message(Command('start', 'help'))
async def send_welcome(message: types.Message):
    await message.reply("Отправь голосовое сообщение на английском — получишь оценку IELTS.")


@dp.message()
async def handle_voice(message: types.Message, bot: Bot):
    if not message.voice:
        return

    file = await bot.get_file(message.voice.file_id)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    user_id = message.from_user.id

    ogg_path = os.path.join(VIDEO_SAVING_PATH, f"voice_{user_id}_{date_str}.ogg")
    mp3_path = os.path.join(VIDEO_SAVING_PATH, f"voice_{user_id}_{date_str}.mp3")

    await bot.download_file(file.file_path, destination=ogg_path)
    logging.info(f"Сохранён ogg: {ogg_path} ({os.path.getsize(ogg_path)} байт)")

    subprocess.run(
        [FFMPEG, "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", "-b:a", "64k", mp3_path],
        check=True,
        capture_output=True,
    )
    logging.info(f"Сконвертирован mp3: {mp3_path} ({os.path.getsize(mp3_path)} байт)")

    await message.answer("Голосовое получено, транскрибирую...")

    try:
        transcript = await transcribe_audio(mp3_path)
    except Exception as e:
        await message.answer(f"Ошибка транскрипции: {e}")
        return

    if not transcript.strip():
        await message.answer("Не удалось распознать речь в аудио.")
        return

    logging.info(f"Транскрипт: {transcript}")
    await message.answer("Транскрипт получен, оцениваю по IELTS...")

    try:
        evaluation = await evaluate_ielts(transcript)
        await message.answer(evaluation)
    except Exception as e:
        await message.answer(f"Ошибка оценки: {e}")


async def main():
    await dp.start_polling(bot, skip_updates=True)


if __name__ == '__main__':
    asyncio.run(main())
