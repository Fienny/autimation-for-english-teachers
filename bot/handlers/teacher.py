import asyncio
import logging
import os
import shutil

from aiogram import Bot, Router, types
from aiogram.filters import Command

from bot.config import VIDEO_SAVING_PATH
from chatgpt_api.gpt import transcribe_audio, evaluate_ielts_teacher

router = Router()

FFMPEG = (
    shutil.which("ffmpeg")
    or r"C:\Users\imfya\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe"
)


@router.message(Command("start", "help"))
async def teacher_start(message: types.Message):
    await message.answer(
        "Панель учителя\n\n"
        "Отправь голосовое ответа ученика — получишь:\n"
        "• Баллы IELTS по 4 критериям\n"
        "• Проверку на аутентичность (бумажка / ИИ)\n"
        "• Топ 3 грамматические ошибки\n"
        "• Топ 10 слов используемых некорректно + замены\n"
        "• Разбор раскрытия идей"
    )


@router.message()
async def teacher_voice(message: types.Message, bot: Bot):
    if not message.voice:
        return

    file = await bot.get_file(message.voice.file_id)
    user_id = message.from_user.id
    unique_id = message.voice.file_id

    ogg_path = os.path.join(VIDEO_SAVING_PATH, f"voice_{user_id}_{unique_id}.ogg")
    mp3_path = os.path.join(VIDEO_SAVING_PATH, f"voice_{user_id}_{unique_id}.mp3")

    await bot.download_file(file.file_path, destination=ogg_path)
    logging.info(f"[teacher] Сохранён ogg: {ogg_path} ({os.path.getsize(ogg_path)} байт)")

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
        logging.error(f"[teacher] Ошибка конвертации ffmpeg для {user_id}: {e}")
        await message.answer("Не удалось обработать аудиофайл. Попробуй ещё раз.")
        return
    finally:
        if os.path.exists(ogg_path):
            os.remove(ogg_path)

    logging.info(f"[teacher] Сконвертирован mp3: {mp3_path} ({os.path.getsize(mp3_path)} байт)")
    await message.answer("Голосовое получено, транскрибирую...")

    try:
        transcript = await transcribe_audio(mp3_path)
    except Exception as e:
        logging.error(f"[teacher] Ошибка транскрипции для {user_id}: {e}")
        await message.answer("Ошибка транскрипции. Попробуй ещё раз.")
        return
    finally:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)

    if not transcript.strip():
        await message.answer("Не удалось распознать речь в аудио.")
        return

    logging.info(f"[teacher] Транскрипт [{user_id}]: {transcript}")
    await message.answer("Транскрипт получен, анализирую...")

    try:
        evaluation = await evaluate_ielts_teacher(transcript)
    except Exception as e:
        logging.error(f"[teacher] Ошибка оценки IELTS для {user_id}: {e}")
        await message.answer("Не удалось получить оценку. Попробуй ещё раз.")
        return

    await message.answer(evaluation, parse_mode="Markdown")
