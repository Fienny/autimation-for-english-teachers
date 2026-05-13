import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command

from bot.config import BOT_TOKEN, GROUP_IDS
from bot.roles import get_user_role
from bot.handlers import student, teacher, group

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------------------------------------------------------------------------
# Роутер для личных сообщений
# ---------------------------------------------------------------------------
private_router = Router()
private_router.message.filter(F.chat.type == "private")


@private_router.message(Command("start", "help"))
async def private_start(message: types.Message) -> None:
    role = await get_user_role(bot, message.from_user.id, context="private_start")
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
async def private_message(message: types.Message) -> None:
    role = await get_user_role(bot, message.from_user.id, context="private_message")
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
# Callback: кнопка "Проверить работу" из /start
# ---------------------------------------------------------------------------

@private_router.callback_query(F.data == "start_check")
async def on_start_check(callback: types.CallbackQuery) -> None:
    role = await get_user_role(bot, callback.from_user.id, context="start_check_callback")
    if role == "teacher":
        await callback.message.answer(
            "Отправь голосовое сообщение ученика — обработаю и дам полный анализ.\n"
            "Можно отправить несколько аудио подряд: подожду 30 секунд и обработаю всё вместе."
        )
    else:
        await student.student_start(callback.message, callback.from_user.id)
    await callback.answer()


# ---------------------------------------------------------------------------
# Роутер для группы
# ---------------------------------------------------------------------------
group_router = Router()
group_router.message.filter(F.chat.id.in_(GROUP_IDS))
group_router.include_router(group.router)

# ---------------------------------------------------------------------------
# Регистрация роутеров
# ---------------------------------------------------------------------------
dp.include_router(private_router)
dp.include_router(student.callback_router)  # callback-кнопки ученика
dp.include_router(teacher.callback_router)  # callback-кнопки учителя
dp.include_router(group_router)


async def main() -> None:
    log_config_summary()
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
