"""
Модерация группы:
  - Мат (русский + английский + узбекский кириллица/латиница)
  Нарушителя баним, пишем в чат причину.
"""
import logging
import re

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
    "сука", "суки", "сучка", "сучки", "сцкан", "суккан",
    "мудак", "мудаки", "мудила",
    "залупа", "манда", "пёзда",
    "шлюха", "шлюхи",
    "дрочить", "дрочит", "дрочун",
    "уёбок", "уёбки",
    "нахуй", "нахуя",
    "ёпт", "ёпть",
    "гандон", "гандона", "гандоны",
    "битч",
}

EN_BAD_WORDS: set[str] = {
    "fuck", "fucker", "fucking", "fucked", "fucks", "fuckin",
    "shit", "shits", "shitty", "bullshit",
    "bitch", "bitches", "bich",
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
    "gandon", "gandona",
    "suk", "sukа",
}

# Узбекский мат — кириллица
UZ_CYR_BAD_WORDS: set[str] = {
    "сика", "сикинг", "сикани", "сикай", "сикайди",
    "амак", "амаки", "амакинг",
    "ибн", "ибни", "ибнинг",
    "қурвой", "қурвоя", "қурвоялар",
    "ороспи", "оросди",
    "бузуқ", "бузуқи",
    "хает", "хаётингни",
    "қотоқ", "қотиқ",
    "ахмоқ", "ахмоқлар",
    "тентак", "тентаклар",
    "ялангоч",
    "итнинг боласи", "ит боласи",
    "эшак", "эшакнинг",
    "чўчқа", "чўчқалар",
    "гандон", "гандона",
}

# Узбекский мат — латиница
UZ_LAT_BAD_WORDS: set[str] = {
    "sika", "siking", "sikani", "sikay", "sikaydi",
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
    "gandon", "gandona",
    "boshinga", "kalvak",
}

ALL_BAD_WORDS = RU_BAD_WORDS | EN_BAD_WORDS | UZ_CYR_BAD_WORDS | UZ_LAT_BAD_WORDS


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
