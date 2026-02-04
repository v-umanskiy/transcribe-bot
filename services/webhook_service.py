from . import telegram_service


async def handle_telegram_webhook_data(data: dict) -> dict:
    try:
        return await _handle_telegram_webhook_data(data)
    except Exception as exc:
        print("Unhandled error while processing Telegram webhook:", exc)
        return {"ok": True}


async def _handle_telegram_webhook_data(data: dict) -> dict:
    message = data.get("message")
    if not message:
        return {"ok": True}

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return {"ok": True}

    reply = "got a voice message" if message.get("voice") else "please send a voice message"
    await telegram_service.send_message(chat_id, reply)
    return {"ok": True}
