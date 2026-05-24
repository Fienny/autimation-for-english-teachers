import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.config import GROUP_IDS

logger = logging.getLogger(__name__)

TEACHER_STATUSES = {"creator", "administrator"}
STUDENT_STATUSES = {"member", "restricted"}


def _status_to_text(status: object) -> str:
    return status.value if hasattr(status, "value") else str(status)


async def get_user_role(bot: Bot, user_id: int, context: str = "access-check") -> str:
    """
    Возвращает роль пользователя в любой разрешённой группе:
      'teacher'  — creator или administrator хотя бы в одной группе
      'student'  — рядовой участник хотя бы в одной группе
      'outsider' — не состоит ни в одной разрешённой группе
    """
    logger.info(
        "[%s] Checking Telegram group access for user_id=%s, configured_group_ids=%s",
        context,
        user_id,
        GROUP_IDS,
    )

    if not GROUP_IDS:
        logger.warning("[%s] Access denied for user_id=%s: no group IDs configured", context, user_id)
        return "outsider"

    is_student = False

    for group_id in GROUP_IDS:
        logger.info("[%s] user_id=%s: checking group_id=%s", context, user_id, group_id)
        try:
            member = await bot.get_chat_member(group_id, user_id)
        except TelegramAPIError as e:
            logger.warning(
                "[%s] user_id=%s group_id=%s: get_chat_member failed: %s: %s",
                context,
                user_id,
                group_id,
                type(e).__name__,
                e,
            )
            continue
        except Exception as e:
            logger.exception(
                "[%s] user_id=%s group_id=%s: unexpected get_chat_member error: %s",
                context,
                user_id,
                group_id,
                type(e).__name__,
            )
            continue

        status = _status_to_text(member.status)
        logger.info(
            "[%s] user_id=%s group_id=%s: get_chat_member status=%s",
            context,
            user_id,
            group_id,
            status,
        )

        if status in TEACHER_STATUSES:
            logger.info(
                "[%s] Access granted for user_id=%s as teacher via group_id=%s",
                context,
                user_id,
                group_id,
            )
            return "teacher"
        if status in STUDENT_STATUSES:
            is_student = True

    role = "student" if is_student else "outsider"
    logger.info("[%s] Final role for user_id=%s: %s", context, user_id, role)
    return role
