import httpx

from . import secret_service

TELEGRAM_BOT_TOKEN = secret_service.get_secret("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
TELEGRAM_FILE_URL = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}"


async def send_message(chat_id: int, text: str):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.post(url, json=payload)
            if not response.is_success:
                print("SEND_MESSAGE_ERROR:", response.status_code, response.text)
        except Exception as exc:
            print("SEND_MESSAGE_ERROR:", repr(exc))


async def download_file_from_telegram(file_id: str) -> bytes | None:
    async with httpx.AsyncClient(timeout=10) as client:
        file_path = await _get_telegram_file_path(client, file_id)
        if not file_path:
            return None

        return await _download_telegram_file(client, file_path)


async def _get_telegram_file_path(client: httpx.AsyncClient, file_id: str) -> str | None:
    url = f"{TELEGRAM_API_URL}/getFile?file_id={file_id}"
    try:
        response = await client.get(url)
    except Exception as exc:
        print("TELEGRAM_GET_FILE_ERROR:", repr(exc))
        return None

    if not response.is_success:
        print("TELEGRAM_GET_FILE_ERROR:", response.status_code, response.text)
        return None

    try:
        payload = response.json()
    except Exception as exc:
        print("TELEGRAM_GET_FILE_JSON_ERROR:", repr(exc))
        return None

    if not payload.get("ok"):
        print("TELEGRAM_GET_FILE_ERROR:", payload)
        return None

    return payload["result"]["file_path"]


async def _download_telegram_file(client: httpx.AsyncClient, file_path: str) -> bytes | None:
    url = f"{TELEGRAM_FILE_URL}/{file_path}"
    try:
        response = await client.get(url)
    except Exception as exc:
        print("TELEGRAM_FILE_DOWNLOAD_ERROR:", repr(exc))
        return None

    if not response.is_success:
        print("TELEGRAM_FILE_DOWNLOAD_ERROR:", response.status_code, response.text)
        return None

    return response.content
