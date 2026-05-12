import logging
import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
VIDEO_SAVING_PATH = os.getenv("VIDEO_SAVING_PATH", "/opt/ielts-bot/savings")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def _parse_group_id(raw_value: str, variable_name: str) -> int:
    """Parse a single Telegram group ID, returning 0 when it is not configured."""
    value = raw_value.strip()
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        logging.warning("Ignoring invalid %s Telegram group ID: %s", variable_name, value)
        return 0


def _parse_group_ids(raw_value: str) -> list[int]:
    """Parse comma-separated Telegram group IDs from environment."""
    group_ids: list[int] = []
    seen: set[int] = set()

    for item in raw_value.split(","):
        group_id = _parse_group_id(item, "GROUP_IDS")
        if group_id and group_id not in seen:
            group_ids.append(group_id)
            seen.add(group_id)

    return group_ids


# GROUP_ID is kept for backward compatibility with existing single-group deployments.
GROUP_ID = _parse_group_id(os.getenv("GROUP_ID", ""), "GROUP_ID")
GROUP_IDS = _parse_group_ids(os.getenv("GROUP_IDS", ""))
if GROUP_ID and GROUP_ID not in GROUP_IDS:
    GROUP_IDS.insert(0, GROUP_ID)

# Создаём папку для аудиофайлов при старте, если её нет
os.makedirs(VIDEO_SAVING_PATH, exist_ok=True)
