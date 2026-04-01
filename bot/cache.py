"""
Simple in-memory TTL cache + async delayed file deletion.
Resets on bot restart — acceptable for this scale.
"""
import asyncio
import logging
import os

_store: dict[str, object] = {}


def cache_set(key: str, value: object, ttl: int) -> None:
    """Store value under key, auto-delete after ttl seconds."""
    _store[key] = value
    asyncio.create_task(_expire(key, ttl))


def cache_get(key: str) -> object | None:
    return _store.get(key)


def cache_del(key: str) -> None:
    _store.pop(key, None)


async def _expire(key: str, ttl: int) -> None:
    await asyncio.sleep(ttl)
    _store.pop(key, None)


async def delete_file_after(path: str, delay: int) -> None:
    """Delete a file from disk after delay seconds."""
    await asyncio.sleep(delay)
    try:
        if os.path.exists(path):
            os.remove(path)
            logging.debug(f"[cache] Удалён файл: {path}")
    except Exception as e:
        logging.warning(f"[cache] Не удалось удалить {path}: {e}")
