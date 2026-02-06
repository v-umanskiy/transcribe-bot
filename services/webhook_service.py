import json
import uuid
from urllib.parse import unquote_plus

from . import s3_service
from . import telegram_service
from . import transcription_aws_service
from . import chunks_table_service
from . import transcription_table_service
from . import sqs_service
from . import whisper_service
from . import gemini_service
from . import google_drive_service
from utils import text_utils


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
    document = message.get("document")
    audio = message.get("audio")
    text = message.get("text") or ""

    if _looks_like_drive_link(text):
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

    if not voice and not document and not audio:
        await telegram_service.send_message(
            chat_id,
            "Please send a voice message or an audio file (.wav, .mp3, .m4a, .flac, .ogg).",
        )
        return {"ok": True}

    file_id, file_key, media_format, file_ext, duration_seconds, file_size_bytes, error_message = _extract_audio_info(
        voice,
        document,
        audio,
    )
    if error_message:
        await telegram_service.send_message(chat_id, error_message)
        return {"ok": True}

    if file_size_bytes is not None and file_size_bytes > 20 * 1024 * 1024:
        await telegram_service.send_message(
            chat_id,
            "This file is too large for Telegram downloads. "
            "Please share a public Google Drive link to the file.",
        )
        return {"ok": True}

    status_message_id = await telegram_service.send_message(chat_id, "Recognizing voice...")

    file_bytes = await telegram_service.download_file_from_telegram(file_id)
    if not file_bytes:
        await telegram_service.send_message(chat_id, "Sorry, I couldn’t download your audio message")
        return {"ok": True}

    file_url, _ = await s3_service.upload_file_to_s3(file_bytes, file_key)
    if not file_url:
        await telegram_service.send_message(chat_id, "Sorry, I couldn’t upload your audio message")
        return {"ok": True}

    if _should_use_whisper(duration_seconds, file_size_bytes):
        try:
            transcript_text = whisper_service.transcribe_audio_bytes(file_bytes, file_ext)
        except Exception as exc:
            print("WHISPER_ERROR:", repr(exc))
            await telegram_service.send_message(chat_id, "Sorry, I couldn’t transcribe your audio message")
            return {"ok": True}
        if status_message_id:
            try:
                await telegram_service.edit_message_text(
                    int(chat_id),
                    int(status_message_id),
                    "Recognizing voice...\nVoice recognized\nRefining...",
                )
            except Exception as exc:
                print("STATUS_EDIT_ERROR:", repr(exc))
        await _process_whisper_text(str(chat_id), transcript_text)
    else:
        job_id = f"tg-{uuid.uuid4()}"
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

    reply = transcripts[0].get("transcript")
    if not reply:
        return {"status": "empty_transcript"}

    return await _process_transcript_text(
        job_id=job_id,
        transcription_job=transcription_job,
        chat_id=str(chat_id),
        transcript_text=reply,
    )


async def _process_transcript_text(
    job_id: str,
    transcription_job: dict | None,
    chat_id: str,
    transcript_text: str,
) -> dict:
    chunks = text_utils.split_into_chunks(transcript_text, max_chars=3000)
    if not chunks:
        return {"status": "empty_transcript"}

    total_chunks = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        await chunks_table_service.save_chunk(job_id, idx, total_chunks, chunk, str(chat_id))

    if transcription_job is None:
        transcription_job = await transcription_table_service.get_by_job_id(job_id)

    await _update_status_after_transcript(transcription_job, total_chunks)
    transcription_table_service.mark_job_done(job_id)
    sqs_service.send_chunk(job_id, 1)
    return {"status": "ok"}


def _looks_like_drive_link(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return "drive.google.com" in lowered or "docs.google.com" in lowered


async def _process_whisper_text(chat_id: str, transcript_text: str) -> dict:
    refined = await gemini_service.refine_text(transcript_text)
    refined = refined.strip() or transcript_text

    parts = text_utils.split_by_length(refined, max_len=3500)
    for part in parts:
        await telegram_service.send_message(int(chat_id), part)

    return {"status": "ok"}


def _extract_audio_info(
    voice: dict | None,
    document: dict | None,
    audio: dict | None,
) -> tuple[str | None, str | None, str | None, str | None, int | None, int | None, str | None]:
    if voice:
        file_id = voice.get("file_id")
        if not file_id:
            return None, None, None, None, None, None, "Please send a voice message or an audio file (.wav, .mp3, .m4a, .flac, .ogg)."
        duration = voice.get("duration")
        file_size = voice.get("file_size")
        file_key = f"voices/{file_id}.ogg"
        return file_id, file_key, "ogg", "ogg", duration, file_size, None

    source = document or audio
    if not source:
        return None, None, None, None, None, None, "Please send a voice message or an audio file (.wav, .mp3, .m4a, .flac, .ogg)."
    file_id = source.get("file_id")
    file_name = (source.get("file_name") or "").lower()
    mime_type = (source.get("mime_type") or "").lower()
    duration = source.get("duration")
    file_size = source.get("file_size")
    ext = ""
    if "." in file_name:
        ext = file_name.rsplit(".", 1)[-1]

    mime_to_ext = {
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/flac": "flac",
        "audio/ogg": "ogg",
        "audio/mp4": "mp4",
        "audio/x-m4a": "m4a",
        "audio/m4a": "m4a",
    }
    if not ext and mime_type in mime_to_ext:
        ext = mime_to_ext[mime_type]

    supported = {"mp3": "mp3", "wav": "wav", "flac": "flac", "ogg": "ogg", "m4a": "mp4", "mp4": "mp4"}
    if ext not in supported or not file_id:
        return None, None, None, None, None, None, "Please send a voice message or an audio file (.wav, .mp3, .m4a, .flac, .ogg)."

    file_key = f"audiofiles/{file_id}.{ext}"
    return file_id, file_key, supported[ext], ext, duration, file_size, None


def _should_use_whisper(duration_seconds: int | None, file_size_bytes: int | None) -> bool:
    if duration_seconds is None:
        return False
    if duration_seconds > 180:
        return False
    if file_size_bytes is None:
        return True
    return file_size_bytes <= 20 * 1024 * 1024


async def _update_status_after_transcript(job: dict | None, total_chunks: int) -> None:
    if not job:
        return
    chat_id = job.get("chat_id")
    message_id = job.get("status_message_id")
    if not chat_id or not message_id:
        return

    status_log = (job.get("status_log") or "").strip()
    lines = [line for line in status_log.split("\n") if line] if status_log else []
    lines.append("Voice recognized")
    if total_chunks > 1:
        lines.append(f"{total_chunks} parts prepared")
    lines.append("Refining...")
    new_log = "\n".join(lines)

    if not transcription_table_service.update_status_log(job["job_id"], new_log):
        return

    try:
        await telegram_service.edit_message_text(int(chat_id), int(message_id), new_log)
    except Exception as exc:
        print("STATUS_EDIT_ERROR:", repr(exc))
