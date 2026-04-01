"""
Модерация группы:
  - Мат (русский + английский + узбекский кириллица/латиница)
  - Ссылки от не-админов
  - Флуд: >5 сообщений за 10 секунд
  - Дубли: одинаковый текст 2 раза подряд
  Нарушителя баним, пишем в чат причину.
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
    "блять", "бля", "блядь", "блядина", "блядский",
    "ёбаный", "ёб", "ебать", "ебал", "ебёт", "ебут", "ебись",
    "ёбнуть", "ёбнул", "ёбнулся",
    "выебать", "выебал", "выебывается",
    "заебать", "заебал", "заебись", "заебало",
    "наебать", "наебал", "наебали",
    "отъебись", "отъебать",
    "пиздец", "пизда", "пиздить", "пиздят", "пиздёж",
    "пиздатый", "пиздануть", "пиздюк", "пиздюли",
    "хуй", "хуйня", "хуйло", "хуесос", "хуеплёт",
    "хуёвый", "нихуя", "похуй",
    "сука", "суки", "сучка", "сучки",
    "мудак", "мудаки", "мудила",
    "залупа", "манда", "пёзда",
    "шлюха", "шлюхи",
    "дрочить", "дрочит", "дрочун",
    "уёбок", "уёбки",
    "нахуй", "нахуя",
    "ёпт", "ёпть",
}

EN_BAD_WORDS: set[str] = {
    "fuck", "fucker", "fucking", "fucked", "fucks", "fuckin",
    "shit", "shits", "shitty", "bullshit",
    "bitch", "bitches",
    "asshole", "assholes",
    "bastard", "bastards",
    "cunt", "cunts",
    "dick", "dicks", "dickhead",
    "pussy", "pussies",
    "cock", "cocks",
    "whore", "whores",
    "nigger", "niggers", "nigga",
    "faggot", "faggots",
    "motherfucker", "motherfucking",
    "wanker", "twat", "slut", "prick",
}

# Узбекский мат — кириллица
UZ_CYR_BAD_WORDS: set[str] = {
    "сика", "сикинг", "сикани",
    "амак", "амаки", "амакинг",
    "ибн", "ибни", "ибнинг",
    "қурвой", "қурвоя", "қурвоялар",
    "ороспи", "оросди",
    "бузуқ", "бузуқи",
    "хает", "хаётингни",
    "уят", "уятсиз",
    "қотоқ", "қотиқ",
    "манқурт",
    "ахмоқ", "ахмоқлар",
    "тентак", "тентаклар",
    "ялангоч",
    "итнинг боласи", "ит боласи",
    "эшак", "эшакнинг",
    "чўчқа", "чўчқалар",
}

# Узбекский мат — латиница
UZ_LAT_BAD_WORDS: set[str] = {
    "sika", "siking", "sikani",
    "amak", "amaki", "amaking",
    "ibn", "ibni", "ibning",
    "qurvoy", "qoʻtoʻs", "qotos",
    "orospi", "orosdi",
    "buzuq", "buzuqi",
    "xaet", "xayotingni",
    "qotoq",
    "axmoq", "axmoqlar",
    "tentak",
    "yalangoʻch", "yalangnch",
    "itning bolasi", "it bolasi",
    "eshak", "eshaking",
    "choʻchqa", "chochqa",
}

ALL_BAD_WORDS = RU_BAD_WORDS | EN_BAD_WORDS | UZ_CYR_BAD_WORDS | UZ_LAT_BAD_WORDS

# ---------------------------------------------------------------------------
# Regex для ссылок
# ---------------------------------------------------------------------------
URL_RE = re.compile(r"(https?://|www\.|t\.me/|tg://|@\w{3,})", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Состояние (in-memory)
# ---------------------------------------------------------------------------
FLOOD_MAX = 5
FLOOD_WINDOW = 10

_flood_data: dict[int, deque] = {}
_last_msg: dict[int, str] = {}


# ---------------------------------------------------------------------------
# Проверки
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    replacements = {"@": "а", "0": "о", "3": "е", "1": "и", "4": "ч", "6": "б", "$": "с"}
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


async def _ban(bot: Bot, message: types.Message, reason: str) -> None:
    name = message.from_user.full_name
    user_id = message.from_user.id
    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"[group] Не удалось удалить сообщение: {e}")
    try:
        await bot.ban_chat_member(message.chat.id, user_id)
    except Exception as e:
        logging.warning(f"[group] Не удалось забанить {user_id}: {e}")
    try:
        await bot.send_message(
            message.chat.id,
            f"🚫 {name} забанен. Причина: {reason}.",
        )
    except Exception as e:
        logging.warning(f"[group] Не удалось отправить сообщение о бане: {e}")
    logging.info(f"[group] Забанен {name} ({user_id}): {reason}")


# ---------------------------------------------------------------------------
# Основной обработчик
# ---------------------------------------------------------------------------

@router.message()
async def moderate(message: types.Message, bot: Bot) -> None:
    text = message.text or message.caption or ""
    user_id = message.from_user.id if message.from_user else None

    if not user_id:
        return

    if await _is_admin(bot, message.chat.id, user_id):
        return

    if text and _contains_profanity(text):
        await _ban(bot, message, "мат")
        return

    if text and _contains_link(text):
        await _ban(bot, message, "ссылки запрещены")
        return

    if _is_flood(user_id):
        await _ban(bot, message, "флуд")
        return

    if text and _is_duplicate(user_id, text):
        await _ban(bot, message, "спам")
        return
