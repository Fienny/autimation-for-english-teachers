import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command

from bot.config import BOT_TOKEN, GROUP_ID
from bot.roles import get_user_role
from bot.handlers import student, teacher, group

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------------------------------------------------------------------------
# Роутер для личных сообщений — определяет роль и передаёт дальше
# ---------------------------------------------------------------------------
private_router = Router()
private_router.message.filter(F.chat.type == "private")


@private_router.message(Command("start", "help"))
async def private_start(message: types.Message):
    role = await get_user_role(bot, message.from_user.id)

    if role == "outsider":
        await message.answer(
            "Доступ закрыт.\n"
            "Ты должен состоять в группе, которую обслуживает этот бот."
        )
        return

    if role == "teacher":
        await teacher.teacher_start(message)
    else:
        await student.student_start(message)


@private_router.message()
async def private_message(message: types.Message):
    role = await get_user_role(bot, message.from_user.id)

    if role == "outsider":
        await message.answer(
            "Доступ закрыт.\n"
            "Ты должен состоять в группе, которую обслуживает этот бот."
        )
        return

    if role == "teacher":
        await teacher.teacher_voice(message, bot)
    else:
        await student.student_voice(message, bot)


# ---------------------------------------------------------------------------
# Роутер для группы — только наша группа
# ---------------------------------------------------------------------------
group_router = Router()
group_router.message.filter(F.chat.id == GROUP_ID)

group_router.include_router(group.router)

# ---------------------------------------------------------------------------
# Регистрация роутеров
# ---------------------------------------------------------------------------
dp.include_router(private_router)
dp.include_router(group_router)


async def main():
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
