"""
Модерация группы:
  - Мат (русский + английский)
  - Ссылки от не-админов
  - Флуд: >5 сообщений за 10 секунд
  - Дубли: одинаковый текст 2 раза подряд
"""
import logging
import re
import time
from collections import deque

from aiogram import Bot, Router, types
from aiogram.enums import ChatMemberStatus

router = Router()

# ---------------------------------------------------------------------------
# Списки запрещённых слов
# ---------------------------------------------------------------------------

RU_BAD_WORDS: set[str] = {
    # --- мат ---
    "блять", "бля", "блядь", "блядина", "блядский",
    "ёбаный", "ёб", "ебать", "ебал", "ебёт", "ебут", "ебись",
    "ёбнуть", "ёбнул", "ёбнулся",
    "выебать", "выебал", "выебывается",
    "заебать", "заебал", "заебись", "заебало",
    "наебать", "наебал", "наебали",
    "отъебись", "отъебать",
    "переёбывать",
    "пиздец", "пизда", "пиздить", "пиздят", "пиздёж",
    "пиздатый", "пиздануть",
    "хуй", "хуйня", "хуйло", "хуесос", "хуеплёт",
    "хуёвый", "нихуя", "похуй", "похуям",
    "ёбнутый",
    "сука", "суки", "сучка", "сучки", "сучий",
    "ёбаная", "ёбаные",
    "мудак", "мудаки", "мудила",
    "залупа", "залупиться",
    "манда", "мандавошка",
    "пёзда",
    "шлюха", "шлюхи",
    "дрочить", "дрочит", "дрочун",
    "ёбать", "ёбнули",
    "пиздануть", "пиздюк", "пиздюли",
    "ёбанный", "въёбывать",
    "ёб твою мать", "иди нахуй", "иди на хуй",
    "нахуй", "нахуя",
    "уёбок", "уёбки",
    "хуесосить",
    "ёпт", "ёпть",
}

EN_BAD_WORDS: set[str] = {
    "fuck", "fucker", "fucking", "fucked", "fucks", "fuckin",
    "shit", "shits", "shitty", "bullshit",
    "bitch", "bitches", "bitchy",
    "asshole", "assholes", "ass",
    "bastard", "bastards",
    "cunt", "cunts",
    "dick", "dicks", "dickhead",
    "pussy", "pussies",
    "cock", "cocks",
    "whore", "whores",
    "nigger", "niggers", "nigga",
    "faggot", "faggots", "fag",
    "motherfucker", "motherfucking",
    "jackass", "dumbass", "dumbfuck",
    "wanker", "wankers",
    "twat", "twats",
    "slut", "sluts",
    "prick", "pricks",
    "retard", "retarded",
    "damn", "goddamn", "god damn",
}

ALL_BAD_WORDS = RU_BAD_WORDS | EN_BAD_WORDS

# ---------------------------------------------------------------------------
# Regex для ссылок
# ---------------------------------------------------------------------------
URL_RE = re.compile(
    r"(https?://|www\.|t\.me/|tg://|@\w{3,})",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Состояние для флуда и дублей (in-memory, сбрасывается при рестарте бота)
# ---------------------------------------------------------------------------
FLOOD_MAX = 5        # максимум сообщений
FLOOD_WINDOW = 10    # за N секунд

_flood_data: dict[int, deque] = {}   # user_id → deque of timestamps
_last_msg: dict[int, str] = {}       # user_id → последний текст


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Приводит текст к нижнему регистру, убирает лишние символы."""
    # Заменяем типичные замены букв: @ → а, 0 → о, 3 → е, 1 → и/л и т.д.
    replacements = {
        "@": "а", "0": "о", "3": "е", "1": "и",
        "4": "ч", "6": "б", "$": "с", "!": "и",
    }
    t = text.lower()
    for k, v in replacements.items():
        t = t.replace(k, v)
    return t


def _contains_profanity(text: str) -> bool:
    normalized = _normalize(text)
    words = re.split(r"[\s\W]+", normalized)
    return any(w in ALL_BAD_WORDS for w in words if w)


def _contains_link(text: str) -> bool:
    return bool(URL_RE.search(text))


def _is_flood(user_id: int) -> bool:
    now = time.monotonic()
    if user_id not in _flood_data:
        _flood_data[user_id] = deque()
    dq = _flood_data[user_id]
    dq.append(now)
    # Убираем старые отметки за пределами окна
    while dq and dq[0] < now - FLOOD_WINDOW:
        dq.popleft()
    return len(dq) > FLOOD_MAX


def _is_duplicate(user_id: int, text: str) -> bool:
    prev = _last_msg.get(user_id)
    _last_msg[user_id] = text
    return prev is not None and prev.strip().lower() == text.strip().lower()


async def _is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
    except Exception:
        return False


async def _punish(bot: Bot, message: types.Message, reason: str):
    """Удаляет сообщение и отправляет предупреждение."""
    name = message.from_user.full_name
    user_id = message.from_user.id
    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"[group] Не удалось удалить сообщение: {e}")
    try:
        await bot.send_message(
            message.chat.id,
            f"⚠️ {name}, твоё сообщение удалено. Причина: {reason}.",
        )
    except Exception as e:
        logging.warning(f"[group] Не удалось отправить предупреждение: {e}")
    logging.info(f"[group] Нарушение от {name} ({user_id}): {reason}")


# ---------------------------------------------------------------------------
# Основной обработчик
# ---------------------------------------------------------------------------

@router.message()
async def moderate(message: types.Message, bot: Bot):
    # Пропускаем сообщения без текста/подписи (фото без подписи, стикеры и т.д.)
    text = message.text or message.caption or ""
    user_id = message.from_user.id if message.from_user else None

    if not user_id:
        return

    # Администраторы группы не модерируются
    if await _is_admin(bot, message.chat.id, user_id):
        return

    # 1. Мат
    if text and _contains_profanity(text):
        await _punish(bot, message, "нецензурная лексика")
        return

    # 2. Ссылки
    if text and _contains_link(text):
        await _punish(bot, message, "ссылки запрещены")
        return

    # 3. Флуд
    if _is_flood(user_id):
        await _punish(bot, message, "флуд")
        return

    # 4. Дубли
    if text and _is_duplicate(user_id, text):
        await _punish(bot, message, "повторяющееся сообщение")
        return
