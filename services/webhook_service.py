import uuid

from . import s3_service
from . import telegram_service
from . import transcription_aws_service
from . import transcription_table_service
from . import sqs_service
from . import whisper_service
from . import gemini_service
from . import quota_service
from utils import text_utils, audio_utils, quota_formatting


async def handle_telegram_webhook_data(data: dict) -> dict:
    try:
        return await _handle_telegram_webhook_data(data)
    except Exception as exc:
        print("Unhandled error while processing Telegram webhook:", exc)
        return {"ok": True}


async def _schedule_google_drive_download(chat_id, text):
    status_message_id = await telegram_service.send_message(chat_id, "Got a link. I'll try to download it.")
    job_id = f"tg-{uuid.uuid4()}"
    await transcription_table_service.save_transcription_job(
        chat_id,
        job_id,
        None,
        None,
        status_message_id,
        "Got a link. I'll try to download it.",
        source_url=text,
    )
    sqs_service.send_drive_download(job_id, text)
    return {"ok": True}


async def _notify_file_too_large(chat_id):
    await telegram_service.send_message(
        chat_id,
        "This file is too large for Telegram downloads. "
        "Please share a public Google Drive link to the file.",
    )


async def _consume_quota_or_notify(chat_id: int | str, file_bytes: bytes, file_ext: str | None) -> bool:
    try:
        result = await quota_service.try_consume_monthly_bytes(
            str(chat_id),
            len(file_bytes),
        )
        if result.allowed:
            print(
                "QUOTA_BYTES_ACCEPTED",
                {
                    "chat_id": str(chat_id),
                    "source": "telegram",
                    "file_ext": file_ext,
                    "bytes": len(file_bytes),
                    "used_bytes": result.used_bytes,
                    "limit_bytes": result.limit_bytes,
                    "quota_policy_version": result.quota_policy_version,
                },
            )
            return True

        print(
            "QUOTA_BYTES_REJECTED",
            {
                "chat_id": str(chat_id),
                "source": "telegram",
                "file_ext": file_ext,
                "bytes": len(file_bytes),
                "used_bytes": result.used_bytes,
                "limit_bytes": result.limit_bytes,
                "quota_policy_version": result.quota_policy_version,
            },
        )
        await telegram_service.send_message(chat_id, quota_formatting.format_quota_exceeded(result))
        return False
    except Exception as exc:
        print(
            "QUOTA_CHECK_ERROR",
            {
                "chat_id": str(chat_id),
                "source": "telegram",
                "file_ext": file_ext,
                "error": repr(exc),
            },
        )
        return True


async def _handle_limit_command(chat_id: int | str) -> dict:
    try:
        status = await quota_service.get_monthly_quota_status(str(chat_id))
        message = quota_formatting.format_quota_status(status)
    except Exception as exc:
        print("LIMIT_COMMAND_ERROR", {"chat_id": str(chat_id), "error": repr(exc)})
        message = "Sorry, I couldn't load your monthly usage right now. Please try again later."

    await telegram_service.send_message(chat_id, message)
    return {"ok": True}


async def _handle_command(chat_id: int | str, text: str) -> dict | None:
    command = text.strip().lower()
    if command == "/limit":
        return await _handle_limit_command(chat_id)
    return None


async def _process_whisper_text(chat_id: str, transcript_text: str) -> dict:
    refined = await gemini_service.refine_text(transcript_text)
    refined = refined.strip() or transcript_text

    parts = text_utils.split_by_length(refined, max_len=3500)
    for part in parts:
        await telegram_service.send_message(int(chat_id), part)

    return {"status": "ok"}


def _whisper_supported_ext(file_ext: str | None) -> bool:
    if not file_ext:
        return False
    ext = file_ext.lower().lstrip(".")
    return ext in {"ogg", "mp3", "wav", "flac"}


async def _handle_telegram_webhook_data(data: dict) -> dict:
    message = data.get("message")
    if not message:
        return {"ok": True}

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return {"ok": True}

    voice = message.get("voice")
    document = message.get("document")
    audio = message.get("audio")
    text = message.get("text") or ""

    command_result = await _handle_command(chat_id, text)
    if command_result is not None:
        return command_result

    if text_utils.looks_like_drive_link(text):
        return await _schedule_google_drive_download(chat_id, text)

    if not voice and not document and not audio:
        await telegram_service.send_message(
            chat_id,
            "Please send a voice message or an audio file (.wav, .mp3, .m4a, .flac, .ogg).",
        )
        return {"ok": True}

    file_id, file_key, media_format, file_ext, duration_seconds, file_size_bytes, error_message = audio_utils.extract_audio_info(
        voice,
        document,
        audio,
    )
    if error_message:
        await telegram_service.send_message(chat_id, error_message)
        return {"ok": True}

    if file_size_bytes is not None and file_size_bytes > 20 * 1024 * 1024:
        await _notify_file_too_large(chat_id)
        return {"ok": True}

    status_message_id = await telegram_service.send_message(chat_id, "Recognizing voice...")

    file_bytes = await telegram_service.download_file_from_telegram(file_id)
    if not file_bytes:
        await telegram_service.send_message(chat_id, "Sorry, I couldn’t download your audio message")
        return {"ok": True}

    if not await _consume_quota_or_notify(chat_id, file_bytes, file_ext):
        if status_message_id:
            await telegram_service.delete_message(int(chat_id), int(status_message_id))
        return {"ok": True}

    file_url, _ = await s3_service.upload_file_to_s3(file_bytes, file_key)
    if not file_url:
        await telegram_service.send_message(chat_id, "Sorry, I couldn’t upload your audio message")
        return {"ok": True}

    job_id = f"tg-{uuid.uuid4()}"

    if _should_use_whisper(duration_seconds, file_size_bytes, file_ext):
        try:
            transcript_text = whisper_service.transcribe_audio_bytes(file_bytes, file_ext)
        except Exception as exc:
            print("WHISPER_ERROR:", repr(exc))
            await transcription_table_service.save_transcription_job(
                chat_id,
                job_id,
                file_url,
                file_key,
                status_message_id,
                "Recognizing voice...",
            )
            transcription_aws_service.transcribe(job_id, file_key, media_format)
            return {"ok": True}
        if status_message_id:
            await telegram_service.edit_message_text(
                int(chat_id),
                int(status_message_id),
                "Recognizing voice...\nVoice recognized\nRefining...",
            )
        await _process_whisper_text(str(chat_id), transcript_text)
        if status_message_id:
            await telegram_service.delete_message(int(chat_id), int(status_message_id))
    else:
        await transcription_table_service.save_transcription_job(
            chat_id,
            job_id,
            file_url,
            file_key,
            status_message_id,
            "Recognizing voice...",
        )
        transcription_aws_service.transcribe(job_id, file_key, media_format)

    return {"ok": True}


def _should_use_whisper(duration_seconds: int | None, file_size_bytes: int | None, file_ext: str | None) -> bool:
    if duration_seconds is None:
        return False
    if duration_seconds > 180:
        return False
    if not _whisper_supported_ext(file_ext):
        return False
    if file_size_bytes is None:
        return True
    return file_size_bytes <= 20 * 1024 * 1024
