import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
VIDEO_SAVING_PATH = os.getenv("VIDEO_SAVING_PATH", "/opt/ielts-bot/savings")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROUP_ID = int(os.getenv("GROUP_ID", "0"))

# Создаём папку для аудиофайлов при старте, если её нет
os.makedirs(VIDEO_SAVING_PATH, exist_ok=True)
