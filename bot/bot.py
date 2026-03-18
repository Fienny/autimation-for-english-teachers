import logging
import asyncio
import shutil
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
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
    user_id = message.from_user.id
    # file_id уникален для каждого аудио — исключает коллизии даже при одновременных запросах
    unique_id = message.voice.file_id

    ogg_path = os.path.join(VIDEO_SAVING_PATH, f"voice_{user_id}_{unique_id}.ogg")
    mp3_path = os.path.join(VIDEO_SAVING_PATH, f"voice_{user_id}_{unique_id}.mp3")

    await bot.download_file(file.file_path, destination=ogg_path)
    logging.info(f"Сохранён ogg: {ogg_path} ({os.path.getsize(ogg_path)} байт)")

    # asyncio.create_subprocess_exec — не блокирует event loop,
    # другие пользователи обрабатываются параллельно пока идёт конвертация
    try:
        process = await asyncio.create_subprocess_exec(
            FFMPEG, "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", "-b:a", "64k", mp3_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(stderr.decode().strip())
    except Exception as e:
        logging.error(f"Ошибка конвертации ffmpeg для {user_id}: {e}")
        await message.answer("Не удалось обработать аудиофайл. Попробуй ещё раз.")
        return
    finally:
        # Удаляем ogg — он больше не нужен
        if os.path.exists(ogg_path):
            os.remove(ogg_path)

    logging.info(f"Сконвертирован mp3: {mp3_path} ({os.path.getsize(mp3_path)} байт)")
    await message.answer("Голосовое получено, транскрибирую...")

    try:
        transcript = await transcribe_audio(mp3_path)
    except Exception as e:
        logging.error(f"Ошибка транскрипции для {user_id}: {e}")
        await message.answer("Ошибка транскрипции. Попробуй ещё раз.")
        return
    finally:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)

    if not transcript.strip():
        await message.answer("Не удалось распознать речь в аудио.")
        return

    logging.info(f"Транскрипт [{user_id}]: {transcript}")
    await message.answer("Транскрипт получен, оцениваю по IELTS...")

    try:
        evaluation = await evaluate_ielts(transcript)
    except Exception as e:
        logging.error(f"Ошибка оценки IELTS для {user_id}: {e}")
        await message.answer("Не удалось получить оценку. Попробуй ещё раз.")
        return

    await message.answer(evaluation)


async def main():
    await dp.start_polling(bot, skip_updates=True)


if __name__ == '__main__':
    asyncio.run(main())
