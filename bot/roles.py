from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from bot.config import GROUP_ID


async def get_user_role(bot: Bot, user_id: int) -> str:
    """
    Возвращает роль пользователя в группе GROUP_ID:
      'teacher'  — creator или administrator
      'student'  — рядовой участник
      'outsider' — не состоит в группе
    """
    if not GROUP_ID:
        return "outsider"

    try:
        member = await bot.get_chat_member(GROUP_ID, user_id)
    except TelegramBadRequest:
        return "outsider"

    status = member.status.value if hasattr(member.status, "value") else str(member.status)

    if status in ("creator", "administrator"):
        return "teacher"
    if status in ("member", "restricted"):
        return "student"
    return "outsider"
