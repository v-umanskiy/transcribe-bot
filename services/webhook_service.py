import uuid

from . import s3_service
from . import telegram_service
from . import transcription_table_service
from . import transcription_aws_service


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

    voice = message.get("voice")
    if not voice:
        await telegram_service.send_message(chat_id, "please send a voice message")
        return {"ok": True}

    file_id = voice.get("file_id")
    if not file_id:
        await telegram_service.send_message(chat_id, "please send a voice message")
        return {"ok": True}

    await telegram_service.send_message(chat_id, "got a voice message")

    file_bytes = await telegram_service.download_file_from_telegram(file_id)
    if not file_bytes:
        await telegram_service.send_message(chat_id, "Sorry, I couldn’t download your voice message")
        return {"ok": True}

    file_key = f"voices/{file_id}.ogg"
    file_url, _ = await s3_service.upload_file_to_s3(file_bytes, file_key)
    if not file_url:
        await telegram_service.send_message(chat_id, "Sorry, I couldn’t upload your voice message")
        return {"ok": True}

    job_id = f"tg-{uuid.uuid4()}"
    await transcription_table_service.save_transcription_job(chat_id, job_id, file_url, file_key)
    transcription_aws_service.transcribe(job_id, file_key)

    return {"ok": True}
