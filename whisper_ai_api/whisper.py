import aiohttp
import asyncio
from .config import BASE_URL, headers

async def send_file(session, path):
    with open(path, "rb") as f:
        data = aiohttp.FormData()
        data.add_field("file", f, filename="voice_266889430_20260318_183025.mp3")

        async with session.post(BASE_URL, headers=headers, data=data) as resp:
            return await resp.json()


async def get_result(session, task_id):
    url = f"{BASE_URL}/{task_id}"

    while True:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()

            if data["status"] == "completed":
                return data["result"]

            if data["status"] == "error":
                return "Ошибка обработки"
        print(data)
        await asyncio.sleep(2)  # НЕ блокирует


async def get_whisper_response(path):
    async with aiohttp.ClientSession() as session:
        data = await send_file(session, path)
        task_id = data["task_id"]

        return await get_result(session, task_id)