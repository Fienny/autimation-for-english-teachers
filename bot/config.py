import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
VIDEO_SAVING_PATH = os.getenv("VIDEO_SAVING_PATH", "/opt/ielts-bot/savings")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Raw group env values are intentionally safe to log: they are Telegram chat IDs,
# not secrets. Tokens and API keys must never be logged.
RAW_GROUP_ID = os.getenv("GROUP_ID", "")
RAW_GROUP_IDS = os.getenv("GROUP_IDS", "")
RAW_ALLOWED_GROUP_IDS = os.getenv("ALLOWED_GROUP_IDS", "")


def _parse_group_id(raw_value: str, variable_name: str) -> int:
    """Parse a single Telegram group ID, returning 0 when it is not configured."""
    value = raw_value.strip()
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        logger.warning("Ignoring invalid %s Telegram group ID: %s", variable_name, value)
        return 0


def _append_unique(group_ids: list[int], seen: set[int], group_id: int) -> None:
    if group_id and group_id not in seen:
        group_ids.append(group_id)
        seen.add(group_id)


def _parse_group_ids(raw_value: str, variable_name: str) -> list[int]:
    """Parse comma-separated Telegram group IDs from environment."""
    group_ids: list[int] = []
    seen: set[int] = set()

    for item in raw_value.split(","):
        group_id = _parse_group_id(item, variable_name)
        if group_id and group_id not in seen:
            group_ids.append(group_id)
            seen.add(group_id)

    return group_ids

def _build_group_ids(group_id: int) -> list[int]:
    """Combine all supported group-id environment variables in priority order."""
    group_ids: list[int] = []
    seen: set[int] = set()

    # GROUP_ID is kept for backward compatibility with existing single-group deployments.
    _append_unique(group_ids, seen, group_id)

    for parsed_group_id in _parse_group_ids(RAW_GROUP_IDS, "GROUP_IDS"):
        _append_unique(group_ids, seen, parsed_group_id)

    # ALLOWED_GROUP_IDS is accepted as an explicit alias because deployments often
    # use this name for allow-lists. GROUP_IDS remains the documented primary name.
    for parsed_group_id in _parse_group_ids(RAW_ALLOWED_GROUP_IDS, "ALLOWED_GROUP_IDS"):
        _append_unique(group_ids, seen, parsed_group_id)

    return group_ids


GROUP_ID = _parse_group_id(RAW_GROUP_ID, "GROUP_ID")
GROUP_IDS = _build_group_ids(GROUP_ID)


def log_config_summary() -> None:
    """Log non-secret startup configuration useful for access debugging."""
    logger.info(
        "Group access config loaded: GROUP_ID=%r, GROUP_IDS=%r, "
        "ALLOWED_GROUP_IDS=%r, effective_group_ids=%s, VIDEO_SAVING_PATH=%r",
        RAW_GROUP_ID,
        RAW_GROUP_IDS,
        RAW_ALLOWED_GROUP_IDS,
        GROUP_IDS,
        VIDEO_SAVING_PATH,
    )
    if not GROUP_IDS:
        logger.warning(
            "No Telegram group IDs configured. Users will be denied access until "
            "GROUP_ID, GROUP_IDS, or ALLOWED_GROUP_IDS is set."
        )


# Создаём папку для аудиофайлов при старте, если её нет
os.makedirs(VIDEO_SAVING_PATH, exist_ok=True)
