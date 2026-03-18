import logging
import subprocess
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import asyncio
from datetime import datetime
from whisper_ai_api.whisper import get_whisper_response
from bot.config import BOT_TOKEN, MY_CHAT_ID, VIDEO_SAVING_PATH

# basic logging
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# temp send hello func - handles onlty given commands
@dp.message(Command('start', 'help'))
async def send_welcome(message: types.Message):
    await message.reply("Hi!\nI'm temp bot's message")

# Circle video saving
@dp.message()
async def save_circle(message: types.Message, bot: Bot):
    if message.voice:
        file = await bot.get_file(message.voice.file_id)

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        user_id = message.from_user.id

        ogg_name = f"voice_{user_id}_{date_str}.ogg"
        mp3_name = f"voice_{user_id}_{date_str}.mp3"

        ogg_path = os.path.join(VIDEO_SAVING_PATH, ogg_name)
        mp3_path = os.path.join(VIDEO_SAVING_PATH, mp3_name)

        # Скачиваем голосовое сообщение (Telegram отдаёт .ogg/opus)
        await bot.download_file(file.file_path, destination=ogg_path)

        # Конвертируем ogg → mp3 через ffmpeg
        subprocess.run(
            ["ffmpeg", "-y", "-i", ogg_path, mp3_path],
            check=True,
            capture_output=True,
        )

        await message.answer("Голосовое получено, транскрибирую...")

        result = await get_whisper_response(mp3_path)
        await message.answer(str(result))

# # temp send message to any command or message (echo)
# @dp.message()
# async def echo(message: types.Message):
#     await message.answer(message.text)

async def main():
    await dp.start_polling(bot, skip_updates=True)

# Loop polling
if __name__ == '__main__':
    asyncio.run(main())