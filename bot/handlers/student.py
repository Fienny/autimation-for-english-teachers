import asyncio
import hashlib
import logging
import os
import shutil

from aiogram import Bot, F, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.cache import delete_file_after
from bot.config import VIDEO_SAVING_PATH
from bot.locks import get_user_lock
from bot.roles import get_user_role
from bot.student_sessions import (
    IeltsPart,
    StudentLanguage,
    StudentSession,
    create_session,
    get_session,
    update_session,
)
from chatgpt_api.gpt import (
    evaluate_student_answer,
    generate_ielts_question,
    split_message,
    transcribe_audio,
)

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
AUDIO_TTL = 30

callback_router = Router()

LANGUAGE_NAMES: dict[StudentLanguage, str] = {
    "ru": "Русский",
    "uz": "O‘zbek",
}

PART_LABELS: dict[IeltsPart, str] = {
    "1": "IELTS Speaking Part 1",
    "2": "IELTS Speaking Part 2",
    "3": "IELTS Speaking Part 3",
}

DETAIL_SECTION_KEYS = {
    "grammar": "GRAMMAR_FEEDBACK",
    "topic": "TOPIC_FEEDBACK",
    "vocab": "VOCABULARY_FEEDBACK",
}

DETAIL_SECTION_TITLES = {
    "ru": {
        "grammar": "📝 Грамматика",
        "topic": "💡 Раскрытие темы",
        "vocab": "📚 Лексика",
    },
    "uz": {
        "grammar": "📝 Grammatika",
        "topic": "💡 Mavzuni ochish",
        "vocab": "📚 Lug‘at / Vocabulary",
    },
}

MESSAGES = {
    "ru": {
        "choose_language": "Выберите язык общения:",
        "choose_part": "Отлично! Теперь выберите часть IELTS Speaking:",
        "generating_question": "Генерирую вопрос для {part}...",
        "question_ready": "Ваш вопрос для {part}:\n\n{question}\n\nОтветьте голосовым сообщением на английском.",
        "question_error": "Не удалось сгенерировать вопрос. Попробуйте выбрать часть ещё раз.",
        "need_start": "Начните тренировку с /start, затем выберите язык и часть IELTS Speaking.",
        "need_part": "Сначала выберите часть IELTS Speaking.",
        "wait_question": "Я ещё генерирую вопрос. Пожалуйста, подождите немного.",
        "processing_previous": "Я обрабатываю предыдущее сообщение, пожалуйста, подождите.",
        "need_voice": "Пожалуйста, ответьте голосовым сообщением.",
        "voice_received": "Голосовое получено, транскрибирую...",
        "convert_error": "Не удалось обработать аудиофайл. Попробуйте ещё раз.",
        "transcription_error": "Не удалось распознать аудио. Попробуйте записать ответ ещё раз.",
        "empty_transcript": "Не удалось распознать речь в аудио. Попробуйте записать ответ ещё раз.",
        "evaluating": "Транскрипт получен, готовлю подробный фидбек...",
        "feedback_error": "Не удалось получить фидбек. Попробуйте отправить ответ ещё раз.",
        "details_prompt": "Выберите, что хотите посмотреть:",
        "session_lost": "Данные попытки не найдены или устарели. Начните новую попытку: выберите часть IELTS Speaking.",
        "empty_section": "В этом разделе сейчас нет дополнительных замечаний.",
    },
    "uz": {
        "choose_language": "Muloqot tilini tanlang:",
        "choose_part": "Ajoyib! Endi IELTS Speaking qismini tanlang:",
        "generating_question": "{part} uchun savol tayyorlayapman...",
        "question_ready": "{part} uchun savolingiz:\n\n{question}\n\nJavobingizni ingliz tilida ovozli xabar qilib yuboring.",
        "question_error": "Savol yaratib bo‘lmadi. Iltimos, qismni yana bir marta tanlang.",
        "need_start": "Mashqni /start orqali boshlang, keyin til va IELTS Speaking qismini tanlang.",
        "need_part": "Avval IELTS Speaking qismini tanlang.",
        "wait_question": "Savol hali tayyorlanmoqda. Iltimos, biroz kuting.",
        "processing_previous": "Oldingi xabarni qayta ishlayapman, iltimos kuting.",
        "need_voice": "Iltimos, javobingizni ovozli xabar qilib yuboring.",
        "voice_received": "Ovozli xabar qabul qilindi, transkripsiya qilyapman...",
        "convert_error": "Audio faylni qayta ishlab bo‘lmadi. Iltimos, yana urinib ko‘ring.",
        "transcription_error": "Audioni tanib bo‘lmadi. Iltimos, javobingizni qayta yozib yuboring.",
        "empty_transcript": "Audioda nutq aniqlanmadi. Iltimos, javobingizni qayta yozib yuboring.",
        "evaluating": "Transkript tayyor, batafsil feedback tayyorlayapman...",
        "feedback_error": "Feedback olishda xatolik yuz berdi. Iltimos, javobingizni qayta yuboring.",
        "details_prompt": "Quyidagilardan birini tanlang:",
        "session_lost": "Urinish ma'lumotlari topilmadi yoki eskirgan. Yangi urinib ko‘ring: IELTS Speaking qismini tanlang.",
        "empty_section": "Bu bo‘limda hozircha qo‘shimcha izoh yo‘q.",
    },
}


def _language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="student:language:ru"),
        InlineKeyboardButton(text="🇺🇿 O‘zbek", callback_data="student:language:uz"),
    ]])


def _parts_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Part 1", callback_data="student:part:1")],
        [InlineKeyboardButton(text="Part 2", callback_data="student:part:2")],
        [InlineKeyboardButton(text="Part 3", callback_data="student:part:3")],
    ])


def _student_detail_keyboard(language: StudentLanguage) -> InlineKeyboardMarkup:
    if language == "uz":
        next_label = "Keyingi savol"
        grammar_label = "Grammatika"
        topic_label = "Mavzuni ochish"
        vocab_label = "Lug‘at / Vocabulary"
    else:
        next_label = "Следующий вопрос"
        grammar_label = "Грамматика"
        topic_label = "Раскрытие темы"
        vocab_label = "Лексика"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=next_label, callback_data="student:detail:next")],
        [InlineKeyboardButton(text=grammar_label, callback_data="student:detail:grammar")],
        [InlineKeyboardButton(text=topic_label, callback_data="student:detail:topic")],
        [InlineKeyboardButton(text=vocab_label, callback_data="student:detail:vocab")],
    ])


def _t(language: StudentLanguage | None, key: str, **kwargs: object) -> str:
    lang = language or "ru"
    return MESSAGES[lang][key].format(**kwargs)


def _parse_student_feedback_sections(raw_feedback: str) -> dict[str, str]:
    markers = [
        "MAIN_FEEDBACK:",
        "VOCABULARY_FEEDBACK:",
        "GRAMMAR_FEEDBACK:",
        "TOPIC_FEEDBACK:",
    ]
    sections: dict[str, str] = {}

    for i, marker in enumerate(markers):
        start = raw_feedback.find(marker)
        if start == -1:
            continue
        content_start = start + len(marker)
        end = len(raw_feedback)
        for next_marker in markers[i + 1:]:
            idx = raw_feedback.find(next_marker, content_start)
            if idx != -1:
                end = idx
                break
        sections[marker[:-1]] = raw_feedback[content_start:end].strip()

    return sections


async def _ensure_student(callback: types.CallbackQuery, bot: Bot) -> bool:
    role = await get_user_role(bot, callback.from_user.id, context="student_callback")
    if role != "student":
        await callback.answer("Доступно только ученикам.", show_alert=True)
        return False
    return True


async def student_start(message: types.Message, user_id: int | None = None) -> None:
    create_session(user_id or message.from_user.id)
    await message.answer(MESSAGES["ru"]["choose_language"], reply_markup=_language_keyboard())


@callback_router.callback_query(F.data.startswith("student:language:"))
async def on_language_selected(callback: types.CallbackQuery, bot: Bot) -> None:
    if not await _ensure_student(callback, bot):
        return

    language = callback.data.rsplit(":", 1)[-1]
    if language not in LANGUAGE_NAMES:
        await callback.answer("Unknown language", show_alert=True)
        return

    session = update_session(
        callback.from_user.id,
        language=language,
        state="choosing_part",
        ielts_part=None,
        question=None,
        transcript=None,
        feedback=None,
        feedback_sections=None,
    )
    await callback.message.answer(_t(session.language, "choose_part"), reply_markup=_parts_keyboard())
    await callback.answer()


@callback_router.callback_query(F.data.startswith("student:part:"))
async def on_part_selected(callback: types.CallbackQuery, bot: Bot) -> None:
    if not await _ensure_student(callback, bot):
        return

    part = callback.data.rsplit(":", 1)[-1]
    if part not in PART_LABELS:
        await callback.answer("Unknown IELTS part", show_alert=True)
        return

    user_id = callback.from_user.id
    session = get_session(user_id)
    if not session or not session.language:
        create_session(user_id)
        await callback.message.answer(MESSAGES["ru"]["choose_language"], reply_markup=_language_keyboard())
        await callback.answer()
        return

    if session.state == "generating_question":
        await callback.message.answer(_t(session.language, "wait_question"))
        await callback.answer()
        return

    if session.state == "processing_answer":
        await callback.message.answer(_t(session.language, "processing_previous"))
        await callback.answer()
        return

    session = update_session(
        user_id,
        ielts_part=part,
        state="generating_question",
        question=None,
        transcript=None,
        feedback=None,
        feedback_sections=None,
    )
    await callback.message.answer(_t(session.language, "generating_question", part=PART_LABELS[part]))
    await callback.answer()

    try:
        question = await generate_ielts_question(part)
    except Exception as e:
        logging.error("[student] Ошибка генерации вопроса для %s: %s", user_id, e)
        update_session(user_id, state="choosing_part", question=None)
        await callback.message.answer(_t(session.language, "question_error"), reply_markup=_parts_keyboard())
        return

    update_session(user_id, state="awaiting_voice", question=question)
    await callback.message.answer(_t(session.language, "question_ready", part=PART_LABELS[part], question=question))


async def student_voice(message: types.Message, bot: Bot) -> None:
    user_id = message.from_user.id
    session = get_session(user_id)

    if not message.voice:
        await _guide_to_current_step(message, session)
        return

    if not session:
        await message.answer(_t(None, "need_start"), reply_markup=_language_keyboard())
        return

    if session.state == "choosing_language" or not session.language:
        await message.answer(MESSAGES["ru"]["choose_language"], reply_markup=_language_keyboard())
        return

    if session.state == "generating_question":
        await message.answer(_t(session.language, "wait_question"))
        return

    if session.state == "processing_answer":
        await message.answer(_t(session.language, "processing_previous"))
        return

    if session.state == "choosing_part" or not session.ielts_part or not session.question:
        await message.answer(_t(session.language, "need_part"), reply_markup=_parts_keyboard())
        return

    if session.state != "awaiting_voice":
        await message.answer(_t(session.language, "choose_part"), reply_markup=_parts_keyboard())
        return

    lock = get_user_lock(user_id)
    if lock.locked():
        await message.answer(_t(session.language, "processing_previous"))
        return

    async with lock:
        fresh_session = get_session(user_id)
        if not _is_ready_for_voice(fresh_session):
            await _guide_to_current_step(message, fresh_session)
            return
        await _process_voice(message, bot, fresh_session)


@callback_router.callback_query(F.data.startswith("student:detail:"))
async def on_student_detail(callback: types.CallbackQuery, bot: Bot) -> None:
    if not await _ensure_student(callback, bot):
        return

    action = callback.data.rsplit(":", 1)[-1]
    user_id = callback.from_user.id
    session = get_session(user_id)

    if not session or not session.language or not session.feedback_sections:
        await callback.answer(_t(None, "session_lost"), show_alert=True)
        await callback.message.answer(_t(None, "session_lost"), reply_markup=_parts_keyboard())
        return

    if action == "next":
        if not session.ielts_part:
            await callback.answer(_t(session.language, "session_lost"), show_alert=True)
            await callback.message.answer(_t(session.language, "session_lost"), reply_markup=_parts_keyboard())
            return
        await callback.message.answer(
            _t(session.language, "generating_question", part=PART_LABELS[session.ielts_part])
        )
        update_session(user_id, state="generating_question", question=None)
        try:
            question = await generate_ielts_question(session.ielts_part)
        except Exception as e:
            logging.error("[student] Ошибка генерации вопроса по кнопке next для %s: %s", user_id, e)
            update_session(user_id, state="choosing_part", question=None)
            await callback.message.answer(_t(session.language, "question_error"), reply_markup=_parts_keyboard())
            await callback.answer()
            return

        update_session(user_id, state="awaiting_voice", question=question)
        await callback.message.answer(
            _t(session.language, "question_ready", part=PART_LABELS[session.ielts_part], question=question)
        )
        await callback.answer()
        return

    marker = DETAIL_SECTION_KEYS.get(action)
    if not marker:
        await callback.answer("Unknown section", show_alert=True)
        return

    section_text = (session.feedback_sections.get(marker) or "").strip()
    if not section_text:
        await callback.answer(_t(session.language, "empty_section"), show_alert=True)
        return

    title = DETAIL_SECTION_TITLES[session.language][action]
    for chunk in split_message(f"{title}\n\n{section_text}"):
        await callback.message.answer(chunk)

    await callback.answer()


async def _guide_to_current_step(message: types.Message, session: StudentSession | None) -> None:
    if not session or not session.language:
        await message.answer(_t(None, "need_start"), reply_markup=_language_keyboard())
        return

    if session.state == "generating_question":
        await message.answer(_t(session.language, "wait_question"))
        return

    if session.state == "awaiting_voice":
        await message.answer(_t(session.language, "need_voice"))
        return

    await message.answer(_t(session.language, "need_part"), reply_markup=_parts_keyboard())


def _is_ready_for_voice(session: StudentSession | None) -> bool:
    return bool(
        session
        and session.state == "awaiting_voice"
        and session.language
        and session.ielts_part
        and session.question
    )


async def _process_voice(message: types.Message, bot: Bot, session: StudentSession) -> None:
    user_id = message.from_user.id
    language = session.language

    update_session(user_id, state="processing_answer")

    file = await bot.get_file(message.voice.file_id)
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
        logging.error("[student] Ошибка конвертации для %s: %s", user_id, e)
        update_session(user_id, state="awaiting_voice")
        await message.answer(_t(language, "convert_error"))
        return
    finally:
        asyncio.create_task(delete_file_after(ogg_path, AUDIO_TTL))

    await message.answer(_t(language, "voice_received"))

    try:
        transcript = await transcribe_audio(mp3_path)
    except Exception as e:
        logging.error("[student] Ошибка транскрипции для %s: %s", user_id, e)
        update_session(user_id, state="awaiting_voice")
        await message.answer(_t(language, "transcription_error"))
        return
    finally:
        asyncio.create_task(delete_file_after(mp3_path, AUDIO_TTL))

    if not transcript.strip():
        update_session(user_id, state="awaiting_voice")
        await message.answer(_t(language, "empty_transcript"))
        return

    await message.answer(_t(language, "evaluating"))

    try:
        feedback = await evaluate_student_answer(
            part=session.ielts_part,
            question=session.question,
            transcript=transcript,
            language=language,
        )
    except Exception as e:
        logging.error("[student] Ошибка оценки для %s: %s", user_id, e)
        update_session(user_id, state="awaiting_voice", transcript=transcript)
        await message.answer(_t(language, "feedback_error"))
        return

    sections = _parse_student_feedback_sections(feedback)
    if not sections:
        sections = {
            "MAIN_FEEDBACK": feedback,
            "VOCABULARY_FEEDBACK": "",
            "GRAMMAR_FEEDBACK": "",
            "TOPIC_FEEDBACK": "",
        }

    main_feedback = sections.get("MAIN_FEEDBACK", "").strip() or feedback

    update_session(
        user_id,
        state="completed",
        transcript=transcript,
        feedback=feedback,
        feedback_sections=sections,
    )

    for chunk in split_message(main_feedback):
        await message.answer(chunk)

    await message.answer(_t(language, "details_prompt"), reply_markup=_student_detail_keyboard(language))
