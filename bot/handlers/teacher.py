import asyncio
import hashlib
import logging
import os
import shutil

from aiogram import Bot, F, Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.cache import cache_set, cache_get, cache_del, delete_file_after
from bot.config import VIDEO_SAVING_PATH
from bot.locks import get_user_lock
from chatgpt_api.gpt import transcribe_audio, evaluate_ielts_teacher, split_message

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

AUDIO_TTL = 30        # секунд — удаляем аудиофайл с диска
RESPONSE_TTL = 1800   # секунд (30 мин) — удаляем кэш секций
BATCH_WINDOW = 30     # секунд ожидания между аудио одного ученика

# Батч-буферы: user_id → список сообщений / задача-таймер
_pending: dict[int, list[types.Message]] = {}
_timers: dict[int, asyncio.Task] = {}

# Callback-роутер для кнопок учителя
callback_router = Router()


# ---------------------------------------------------------------------------
# Клавиатура
# ---------------------------------------------------------------------------

def _detail_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Аутентичность", callback_data="detail:authenticity"),
            InlineKeyboardButton(text="📝 Грамматика",    callback_data="detail:grammar"),
        ],
        [
            InlineKeyboardButton(text="📚 Словарь",       callback_data="detail:vocabulary"),
            InlineKeyboardButton(text="💡 Идеи",          callback_data="detail:ideas"),
        ],
        [
            InlineKeyboardButton(text="✅ Завершить работу", callback_data="detail:done"),
        ],
    ])


# ---------------------------------------------------------------------------
# /start приветствие
# ---------------------------------------------------------------------------

def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📝 Проверить работу", callback_data="start_check")
    ]])


async def teacher_start(message: types.Message) -> None:
    await message.answer(
        "Панель учителя\n\n"
        "Нажми кнопку ниже и отправь голосовое сообщение ученика — получишь полный анализ:\n"
        "• Баллы IELTS\n"
        "• Проверку на аутентичность (бумажка / ИИ)\n"
        "• Топ-3 грамматические ошибки\n"
        "• Топ-10 слов используемых некорректно\n"
        "• Разбор раскрытия идей",
        reply_markup=_start_keyboard(),
    )


# ---------------------------------------------------------------------------
# Приём аудио с батч-окном 30 сек
# ---------------------------------------------------------------------------

async def teacher_voice(message: types.Message, bot: Bot) -> None:
    if not message.voice:
        return

    user_id = message.from_user.id

    if user_id not in _pending:
        _pending[user_id] = []

    _pending[user_id].append(message)
    count = len(_pending[user_id])

    # Отменяем предыдущий таймер
    if user_id in _timers and not _timers[user_id].done():
        _timers[user_id].cancel()

    if count == 1:
        await message.answer(
            "Аудио получено. Жду ещё 30 секунд — "
            "если отправишь ещё аудио этого ученика, обработаю всё вместе."
        )
    else:
        await message.answer(f"Аудио #{count} получено. Таймер сброшен, жду ещё 30 секунд.")

    _timers[user_id] = asyncio.create_task(_process_after_delay(user_id, bot))


async def _process_after_delay(user_id: int, bot: Bot) -> None:
    await asyncio.sleep(BATCH_WINDOW)

    messages = _pending.pop(user_id, [])
    _timers.pop(user_id, None)

    if not messages:
        return

    lock = get_user_lock(user_id)
    async with lock:
        await _process_batch(messages, bot)


# ---------------------------------------------------------------------------
# Обработка батча
# ---------------------------------------------------------------------------

async def _process_batch(messages: list[types.Message], bot: Bot) -> None:
    user_id = messages[0].from_user.id
    notify = messages[-1]  # отвечаем в последнее сообщение

    transcripts: list[str] = []

    for i, msg in enumerate(messages, 1):
        file = await bot.get_file(msg.voice.file_id)
        safe_id = hashlib.md5(msg.voice.file_id.encode()).hexdigest()[:12]

        ogg_path = os.path.join(VIDEO_SAVING_PATH, f"voice_{user_id}_{safe_id}.ogg")
        mp3_path = os.path.join(VIDEO_SAVING_PATH, f"voice_{user_id}_{safe_id}.mp3")

        await bot.download_file(file.file_path, destination=ogg_path)

        try:
            proc = await asyncio.create_subprocess_exec(
                FFMPEG, "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", "-b:a", "64k", mp3_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(stderr.decode().strip())
        except Exception as e:
            logging.error(f"[teacher] Ошибка конвертации аудио #{i} для {user_id}: {e}")
            await notify.answer(f"Не удалось обработать аудио #{i}. Попробуй ещё раз.")
            return
        finally:
            asyncio.create_task(delete_file_after(ogg_path, AUDIO_TTL))

        try:
            text = await transcribe_audio(mp3_path)
        except Exception as e:
            logging.error(f"[teacher] Ошибка транскрипции аудио #{i} для {user_id}: {e}")
            await notify.answer(f"Ошибка транскрипции аудио #{i}. Попробуй ещё раз.")
            return
        finally:
            asyncio.create_task(delete_file_after(mp3_path, AUDIO_TTL))

        if text.strip():
            transcripts.append(text)

    if not transcripts:
        await notify.answer("Не удалось распознать речь ни в одном аудио.")
        return

    combined = "\n\n".join(
        f"[Part {i}]\n{t}" for i, t in enumerate(transcripts, 1)
    ) if len(transcripts) > 1 else transcripts[0]

    logging.info(f"[teacher] Транскрипт [{user_id}]: {combined[:200]}...")
    await notify.answer("Транскрипт получен, анализирую...")

    try:
        sections = await evaluate_ielts_teacher(combined)
    except Exception as e:
        logging.error(f"[teacher] Ошибка оценки для {user_id}: {e}")
        await notify.answer("Не удалось получить оценку. Попробуй ещё раз.")
        return

    # Кэшируем секции на 30 минут
    cache_set(f"teacher:{user_id}", sections, RESPONSE_TTL)

    # Отправляем overview + кнопки
    overview = sections.get("overview", "—")
    for chunk in split_message(overview):
        await notify.answer(chunk)
    await notify.answer(
        "Выбери секцию для подробного разбора:",
        reply_markup=_detail_keyboard(),
    )


# ---------------------------------------------------------------------------
# Callback-обработчики кнопок
# ---------------------------------------------------------------------------

SECTION_LABELS = {
    "authenticity": "🔍 Аутентичность",
    "grammar":      "📝 Грамматика",
    "vocabulary":   "📚 Словарь",
    "ideas":        "💡 Идеи",
}


@callback_router.callback_query(F.data.startswith("detail:"))
async def handle_detail(callback: types.CallbackQuery) -> None:
    section = callback.data.split(":")[1]
    user_id = callback.from_user.id

    if section == "done":
        cache_del(f"teacher:{user_id}")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Работа по данному аудио завершена.")
        await callback.answer()
        return

    data = cache_get(f"teacher:{user_id}")
    if not data:
        await callback.answer(
            "Данные устарели (прошло более 30 минут). Отправьте аудио заново.",
            show_alert=True,
        )
        return

    section_text = data.get(section)
    if not section_text:
        await callback.answer("Раздел не найден.", show_alert=True)
        return

    label = SECTION_LABELS.get(section, section)
    for chunk in split_message(f"*{label}*\n\n{section_text}"):
        await callback.message.answer(chunk, parse_mode="Markdown")

    await callback.answer()
