import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
VIDEO_SAVING_PATH = os.getenv("VIDEO_SAVING_PATH", "/opt/ielts-bot/savings")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
# ID группы, которую обслуживает бот (число, например -1001234567890)
GROUP_ID = int(os.getenv("GROUP_ID", "0"))
