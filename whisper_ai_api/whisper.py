import os
import aiohttp
import asyncio
from .config import BASE_URL, RESULT_URL, headers


async def send_file(session, path):
    with open(path, "rb") as f:
        data = aiohttp.FormData()
        data.add_field("file", f, filename=os.path.basename(path))

        async with session.post(BASE_URL, headers=headers, data=data) as resp:
            return await resp.json()


async def get_result(session, task_id):
    url = f"{RESULT_URL}/{task_id}"
    max_attempts = 60  # до 3 минут (60 × 3s)

    for attempt in range(max_attempts):
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()

        if data.get("status") == "completed":
            return data.get("result") or ""

        if data.get("status") in ("error", "failed"):
            error_detail = data.get("error") or data
            return f"Ошибка обработки: {error_detail}"

        print(f"[whisper] попытка {attempt + 1}/{max_attempts}: {data}")
        await asyncio.sleep(3)

    return "Превышено время ожидания транскрипции"


async def get_whisper_response(path):
    async with aiohttp.ClientSession() as session:
        data = await send_file(session, path)

        if "task_id" not in data:
            return f"Ошибка отправки файла: {data}"

        task_id = data["task_id"]
        return await get_result(session, task_id)