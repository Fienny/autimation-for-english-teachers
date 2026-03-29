import asyncio
import hashlib
import logging
import os
import shutil

from aiogram import Bot, Router, types
from aiogram.filters import Command

from bot.config import VIDEO_SAVING_PATH
from bot.locks import get_user_lock
from chatgpt_api.gpt import transcribe_audio, evaluate_ielts, split_message

router = Router()

os.makedirs(VIDEO_SAVING_PATH, exist_ok=True)

FFMPEG = (
    shutil.which("ffmpeg")
    or r"C:\Users\imfya\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe"
)


@router.message(Command("start", "help"))
async def student_start(message: types.Message):
    await message.answer(
        "Привет! Отправь голосовое сообщение на английском — получишь оценку IELTS."
    )


@router.message()
async def student_voice(message: types.Message, bot: Bot):
    if not message.voice:
        return

    lock = get_user_lock(message.from_user.id)
    if lock.locked():
        await message.answer("Обрабатываю предыдущее сообщение, подожди...")
    async with lock:
        await _process_voice(message, bot)


async def _process_voice(message: types.Message, bot: Bot):
    file = await bot.get_file(message.voice.file_id)
    user_id = message.from_user.id
    safe_id = hashlib.md5(message.voice.file_id.encode()).hexdigest()[:12]

    ogg_path = os.path.join(VIDEO_SAVING_PATH, f"voice_{user_id}_{safe_id}.ogg")
    mp3_path = os.path.join(VIDEO_SAVING_PATH, f"voice_{user_id}_{safe_id}.mp3")

    await bot.download_file(file.file_path, destination=ogg_path)
    logging.info(f"[student] Сохранён ogg: {ogg_path} ({os.path.getsize(ogg_path)} байт)")

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
        logging.error(f"[student] Ошибка конвертации ffmpeg для {user_id}: {e}")
        await message.answer("Не удалось обработать аудиофайл. Попробуй ещё раз.")
        return
    finally:
        if os.path.exists(ogg_path):
            os.remove(ogg_path)

    logging.info(f"[student] Сконвертирован mp3: {mp3_path} ({os.path.getsize(mp3_path)} байт)")
    await message.answer("Голосовое получено, транскрибирую...")

    try:
        transcript = await transcribe_audio(mp3_path)
    except Exception as e:
        logging.error(f"[student] Ошибка транскрипции для {user_id}: {e}")
        await message.answer("Ошибка транскрипции. Попробуй ещё раз.")
        return
    finally:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)

    if not transcript.strip():
        await message.answer("Не удалось распознать речь в аудио.")
        return

    logging.info(f"[student] Транскрипт [{user_id}]: {transcript}")
    await message.answer("Транскрипт получен, оцениваю по IELTS...")

    try:
        evaluation = await evaluate_ielts(transcript)
    except Exception as e:
        logging.error(f"[student] Ошибка оценки IELTS для {user_id}: {e}")
        await message.answer("Не удалось получить оценку. Попробуй ещё раз.")
        return

    for chunk in split_message(evaluation):
        await message.answer(chunk)
