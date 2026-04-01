import asyncio
import hashlib
import logging
import os
import shutil

from aiogram import Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.cache import cache_set, delete_file_after
from bot.config import VIDEO_SAVING_PATH
from bot.locks import get_user_lock
from chatgpt_api.gpt import transcribe_audio, evaluate_ielts, split_message

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

AUDIO_TTL = 30       # секунд — удаляем аудиофайл
RESPONSE_TTL = 1800  # секунд (30 мин) — удаляем кэш ответа


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📝 Проверить работу", callback_data="start_check")
    ]])


async def student_start(message: types.Message) -> None:
    await message.answer(
        "Привет! Нажми кнопку ниже, отправь голосовое сообщение на английском — и получишь фидбек по IELTS.",
        reply_markup=start_keyboard(),
    )


async def student_voice(message: types.Message, bot: Bot) -> None:
    if not message.voice:
        return

    lock = get_user_lock(message.from_user.id)
    if lock.locked():
        await message.answer("Обрабатываю предыдущее сообщение, подожди...")
    async with lock:
        await _process_voice(message, bot)


async def _process_voice(message: types.Message, bot: Bot) -> None:
    file = await bot.get_file(message.voice.file_id)
    user_id = message.from_user.id
    safe_id = hashlib.md5(message.voice.file_id.encode()).hexdigest()[:12]

    ogg_path = os.path.join(VIDEO_SAVING_PATH, f"voice_{user_id}_{safe_id}.ogg")
    mp3_path = os.path.join(VIDEO_SAVING_PATH, f"voice_{user_id}_{safe_id}.mp3")

    await bot.download_file(file.file_path, destination=ogg_path)

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
        logging.error(f"[student] Ошибка конвертации для {user_id}: {e}")
        await message.answer("Не удалось обработать аудиофайл. Попробуй ещё раз.")
        return
    finally:
        asyncio.create_task(delete_file_after(ogg_path, AUDIO_TTL))

    await message.answer("Голосовое получено, транскрибирую...")

    try:
        transcript = await transcribe_audio(mp3_path)
    except Exception as e:
        logging.error(f"[student] Ошибка транскрипции для {user_id}: {e}")
        await message.answer("Ошибка транскрипции. Попробуй ещё раз.")
        return
    finally:
        asyncio.create_task(delete_file_after(mp3_path, AUDIO_TTL))

    if not transcript.strip():
        await message.answer("Не удалось распознать речь в аудио.")
        return

    logging.info(f"[student] Транскрипт [{user_id}]: {transcript}")
    await message.answer("Транскрипт получен, оцениваю...")

    try:
        evaluation = await evaluate_ielts(transcript)
    except Exception as e:
        logging.error(f"[student] Ошибка оценки для {user_id}: {e}")
        await message.answer("Не удалось получить оценку. Попробуй ещё раз.")
        return

    # Кэшируем транскрипт + ответ на 30 минут
    cache_set(f"student:{user_id}", {"transcript": transcript, "evaluation": evaluation}, RESPONSE_TTL)

    for chunk in split_message(evaluation):
        await message.answer(chunk)

    await message.answer("Работа с данным аудио завершена. Пожалуйста, отправьте новое аудиосообщение.")
