from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from bot.config import GROUP_IDS


async def get_user_role(bot: Bot, user_id: int) -> str:
    """
    Возвращает роль пользователя в любой разрешённой группе:
      'teacher'  — creator или administrator хотя бы в одной группе
      'student'  — рядовой участник хотя бы в одной группе
      'outsider' — не состоит ни в одной разрешённой группе
    """
    if not GROUP_IDS:
        return "outsider"

    is_student = False

    for group_id in GROUP_IDS:
        try:
            member = await bot.get_chat_member(group_id, user_id)
        except TelegramAPIError:
            continue

        status = member.status.value if hasattr(member.status, "value") else str(member.status)

        if status in ("creator", "administrator"):
            return "teacher"
        if status in ("member", "restricted"):
            is_student = True

    return "student" if is_student else "outsider"
