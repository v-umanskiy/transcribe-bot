import httpx

from . import secret_service

TELEGRAM_BOT_TOKEN = secret_service.get_secret("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


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
