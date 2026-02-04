import json
import uuid
from urllib.parse import unquote_plus

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


async def handle_transcription_data(event: dict) -> dict:
    try:
        return await _handle_transcription_data(event)
    except Exception as exc:
        print("Unhandled error while processing transcription event:", exc)
        return {"ok": True}


async def _handle_transcription_data(event: dict) -> dict:
    obj_key = unquote_plus(event["detail"]["object"]["key"])

    file_bytes = await s3_service.download_file_from_s3(obj_key)
    if file_bytes is None:
        return {"status": "download_failed"}

    try:
        transcript_json = json.loads(file_bytes)
    except json.JSONDecodeError:
        return {"status": "invalid_json"}

    job_id = transcript_json.get("jobName")
    if not job_id:
        return {"status": "missing_job_name"}

    transcription_job = await transcription_table_service.get_by_job_id(job_id)
    if not transcription_job:
        return {"status": "missing_transcription_job"}

    if transcription_job.get("status") != "pending":
        return {"status": "already_processed"}

    chat_id = transcription_job.get("chat_id")
    if not chat_id:
        return {"status": "missing_chat_id"}

    transcripts = transcript_json.get("results", {}).get("transcripts", [])
    if not transcripts:
        return {"status": "empty_transcript"}

    if not transcription_table_service.mark_job_done(job_id):
        return {"status": "already_processed"}

    reply = transcripts[0].get("transcript")
    if not reply:
        return {"status": "empty_transcript"}

    await _send_long_message(int(chat_id), reply)

    return {"status": "ok"}


async def _send_long_message(chat_id: int, text: str):
    chunk_size = 3500
    for start in range(0, len(text), chunk_size):
        await telegram_service.send_message(chat_id, text[start:start + chunk_size])
