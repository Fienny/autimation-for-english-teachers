import asyncio
import hashlib
import logging
import os
import re
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
    "grammar": "Grammar Range and Accuracy",
    "topic": "Task Response / Topic Development",
    "vocab": "Lexical Resource",
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
        "part2_duration_hint": "Для Part 2 постарайтесь говорить от 1 до 2 минут.",
        "question_error": "Не удалось сгенерировать вопрос. Попробуйте выбрать часть ещё раз.",
        "need_start": "Начните тренировку с /start, затем выберите язык и часть IELTS Speaking.",
        "need_part": "Сначала выберите часть IELTS Speaking.",
        "wait_question": "Я ещё генерирую вопрос. Пожалуйста, подождите немного.",
        "processing_previous": "Я обрабатываю предыдущее сообщение, пожалуйста, подождите.",
        "need_voice": "Пожалуйста, ответьте голосовым сообщением.",
        "voice_received": "Голосовое получено, транскрибирую...",
        "convert_error": "Не удалось обработать аудиофайл. Попробуйте ещё раз.",
        "transcription_error": "Не удалось распознать аудио. Пожалуйста, перезапишите ответ, желательно с другого устройства или микрофона.",
        "empty_transcript": "Не удалось распознать аудио. Пожалуйста, перезапишите ответ, желательно с другого устройства или микрофона.",
        "part2_too_short": "Ответ слишком короткий для Part 2. Нужно говорить минимум 1 минуту. Пожалуйста, перезапишите ответ по тому же вопросу.",
        "part2_too_long": "Ответ слишком длинный для Part 2. Максимум — 3 минуты. Пожалуйста, перезапишите ответ по тому же вопросу.",
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
        "part2_duration_hint": "Part 2 uchun 1 dan 2 daqiqagacha gapirishga harakat qiling.",
        "question_error": "Savol yaratib bo‘lmadi. Iltimos, qismni yana bir marta tanlang.",
        "need_start": "Mashqni /start orqali boshlang, keyin til va IELTS Speaking qismini tanlang.",
        "need_part": "Avval IELTS Speaking qismini tanlang.",
        "wait_question": "Savol hali tayyorlanmoqda. Iltimos, biroz kuting.",
        "processing_previous": "Oldingi xabarni qayta ishlayapman, iltimos kuting.",
        "need_voice": "Iltimos, javobingizni ovozli xabar qilib yuboring.",
        "voice_received": "Ovozli xabar qabul qilindi, transkripsiya qilyapman...",
        "convert_error": "Audio faylni qayta ishlab bo‘lmadi. Iltimos, yana urinib ko‘ring.",
        "transcription_error": "Audioni aniqlab bo‘lmadi. Iltimos, javobni qayta yozing, imkon bo‘lsa boshqa qurilma yoki mikrofondan foydalaning.",
        "empty_transcript": "Audioni aniqlab bo‘lmadi. Iltimos, javobni qayta yozing, imkon bo‘lsa boshqa qurilma yoki mikrofondan foydalaning.",
        "part2_too_short": "Part 2 uchun javob juda qisqa. Kamida 1 daqiqa gapirish kerak. Iltimos, shu savol bo‘yicha javobni qayta yozing.",
        "part2_too_long": "Part 2 uchun javob juda uzun. Maksimum 3 daqiqa. Iltimos, shu savol bo‘yicha javobni qayta yozing.",
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
AUDIO_TTL = 30  # секунд — удаляем аудиофайл

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
        "Estimated IELTS Band:",
        "Task Response / Topic Development:",
        "Fluency and Coherence:",
        "Lexical Resource:",
        "Grammar Range and Accuracy:",
        "Pronunciation / Delivery Notes:",
        "Corrected Answer:",
        "How to Improve:",
    ]
    normalized = raw_feedback
    for marker in markers:
        bare = re.escape(marker)
        with_bold = re.escape(f"**{marker}**")
        normalized = re.sub(with_bold, marker, normalized, flags=re.IGNORECASE)
        normalized = re.sub(rf"^\s*\*\*{bare}\*\*\s*$", marker, normalized, flags=re.IGNORECASE | re.MULTILINE)

    sections: dict[str, str] = {}
    for i, marker in enumerate(markers):
        pattern = re.compile(rf"^\s*{re.escape(marker)}\s*$", flags=re.IGNORECASE | re.MULTILINE)
        start_match = pattern.search(normalized)
        if not start_match:
            continue
        content_start = start_match.end()
        end = len(normalized)
        for next_marker in markers[i + 1:]:
            next_pattern = re.compile(rf"^\s*{re.escape(next_marker)}\s*$", flags=re.IGNORECASE | re.MULTILINE)
            next_match = next_pattern.search(normalized, content_start)
            if next_match:
                end = next_match.start()
                break
        content = normalized[content_start:end].strip()
        sections[marker[:-1]] = content
    return sections


def _sections_have_content(sections: dict[str, str]) -> bool:
    required = [
        "Estimated IELTS Band",
        "Task Response / Topic Development",
        "Fluency and Coherence",
        "Lexical Resource",
        "Grammar Range and Accuracy",
        "Pronunciation / Delivery Notes",
        "Corrected Answer",
        "How to Improve",
    ]
    return all((sections.get(key) or "").strip() for key in required)


def _parse_student_feedback_sections_example() -> None:
    """Local parser sanity example (not used in runtime)."""
    sample = (
        "**Estimated IELTS Band:**\nBand 6.0 overall.\n\n"
        "**Task Response / Topic Development:**\nYou answered the question, but lacked examples.\n\n"
        "**Fluency and Coherence:**\nMostly clear with some pauses.\n\n"
        "**Lexical Resource:**\nUsed simple vocabulary repeatedly.\n\n"
        "**Grammar Range and Accuracy:**\nSeveral tense errors appeared.\n\n"
        "**Pronunciation / Delivery Notes:**\nTranscript-only review; precise pronunciation needs audio.\n\n"
        "**Corrected Answer:**\nI usually spend my free time reading books and jogging.\n\n"
        "**How to Improve:**\nAdd 2 concrete examples and vary linking words."
    )
    parsed = _parse_student_feedback_sections(sample)
    assert _sections_have_content(parsed)


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
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        # It's safe to continue if the original message can't be edited.
        pass

    await callback.message.answer(_t(session.language, "generating_question", part=PART_LABELS[part]))
    await callback.answer()

    try:
        question = await generate_ielts_question(part)
    except Exception as e:
        logging.error("[student] Ошибка генерации вопроса для %s: %s", user_id, e)
        update_session(user_id, state="choosing_part", question=None)
        await callback.message.answer(_t(session.language, "question_error"), reply_markup=_parts_keyboard())
        return

    await _send_question(callback.message, user_id=user_id, language=session.language, part=part, question=question)


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
        update_session(
            user_id,
            state="choosing_part",
            question=None,
            transcript=None,
            feedback=None,
            feedback_sections=None,
        )
        await callback.message.answer(_t(session.language, "choose_part"), reply_markup=_parts_keyboard())
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

    if session.ielts_part == "2" and message.voice:
        duration = message.voice.duration or 0
        if duration < 60:
            update_session(user_id, state="awaiting_voice")
            await message.answer(_t(language, "part2_too_short"))
            return
        if duration > 180:
            update_session(user_id, state="awaiting_voice")
            await message.answer(_t(language, "part2_too_long"))
            return

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
    if not sections or not _sections_have_content(sections):
        sections = {
            "Estimated IELTS Band": "",
            "Task Response / Topic Development": "",
            "Fluency and Coherence": "",
            "Lexical Resource": "",
            "Grammar Range and Accuracy": "",
            "Pronunciation / Delivery Notes": "",
            "Corrected Answer": "",
            "How to Improve": feedback,
        }

    parsed_ok = _sections_have_content(sections)
    main_feedback = (
        "\n\n".join(
            part for part in [
                f"Estimated IELTS Band:\n{sections.get('Estimated IELTS Band', '').strip()}".strip(),
                f"Task Response / Topic Development:\n{sections.get('Task Response / Topic Development', '').strip()}".strip(),
                f"Fluency and Coherence:\n{sections.get('Fluency and Coherence', '').strip()}".strip(),
            ] if part and not part.endswith(":\n")
        ) if parsed_ok else feedback
    ) or feedback

    update_session(
        user_id,
        state="completed",
        transcript=transcript,
        feedback=feedback,
        feedback_sections=sections if parsed_ok else None,
    )

    for chunk in split_message(main_feedback):
        await message.answer(chunk)

    if parsed_ok:
        await message.answer(_t(language, "details_prompt"), reply_markup=_student_detail_keyboard(language))


async def _send_question(
    message: types.Message,
    *,
    user_id: int,
    language: StudentLanguage,
    part: IeltsPart,
    question: str,
) -> None:
    update_session(user_id, ielts_part=part, state="awaiting_voice", question=question)
    await message.answer(_t(language, "question_ready", part=PART_LABELS[part], question=question))
    if part == "2":
        await message.answer(_t(language, "part2_duration_hint"))
