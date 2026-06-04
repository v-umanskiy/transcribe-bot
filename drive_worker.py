import asyncio
import json

from services import google_drive_service
from services import s3_service
from services import transcription_aws_service
from services import transcription_table_service
from services import telegram_service
from services import quota_service
from utils import quota_formatting
from utils.constants import DRIVE_DOWNLOAD_FAILED_MESSAGE, DRIVE_FILE_TOO_LARGE_MESSAGE

MAX_DRIVE_FILE_BYTES = 70 * 1024 * 1024


def handler(event, _context):
    print("SQS_EVENT:", event)
    asyncio.run(_handle_records(event.get("Records") or []))
    return {"ok": True}


async def _handle_records(records: list[dict]):
    for record in records:
        body = record.get("body") or ""
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            print("SQS_BODY_INVALID_JSON:", body)
            continue

        if payload.get("type") != "drive":
            print("SQS_BODY_UNSUPPORTED_TYPE:", payload)
            continue

        job_id = payload.get("job_id")
        url = payload.get("url")
        if not job_id or not url:
            print("SQS_BODY_MISSING_FIELDS:", payload)
            continue

        file_bytes, file_name, file_id, error = await google_drive_service.download_public_file(
            url,
            max_bytes=MAX_DRIVE_FILE_BYTES,
        )
        if error == "file_too_large":
            print("DRIVE_FILE_TOO_LARGE:", url)
            await _append_status(
                job_id,
                DRIVE_FILE_TOO_LARGE_MESSAGE,
            )
            continue
        if not file_bytes or not file_name or not file_id:
            print("DRIVE_DOWNLOAD_FAILED:", url)
            await _append_status(
                job_id,
                DRIVE_DOWNLOAD_FAILED_MESSAGE,
            )
            continue

        drive_info = _extract_drive_file_info(file_name)
        if drive_info is None:
            print("DRIVE_UNSUPPORTED_FILE:", file_name)
            await _append_status(
                job_id,
                DRIVE_DOWNLOAD_FAILED_MESSAGE,
            )
            continue

        await _append_status(job_id, "Downloaded file\nProcessing...")

        media_format, file_ext = drive_info
        file_key = f"audiofiles/drive-{file_id}.{file_ext}"

        if not await _consume_quota_or_update_status(job_id, file_bytes, file_ext):
            continue

        file_url, _ = await s3_service.upload_file_to_s3(file_bytes, file_key)
        if not file_url:
            print("S3_UPLOAD_FAILED:", file_key)
            continue

        transcription_table_service.update_job_file_info(job_id, file_url, file_key)
        await _append_status(job_id, "Recognizing voice...")
        transcription_aws_service.transcribe(job_id, file_key, media_format)


def _extract_drive_file_info(file_name: str) -> tuple[str, str] | None:
    file_name_lower = file_name.lower()
    ext = ""
    if "." in file_name_lower:
        ext = file_name_lower.rsplit(".", 1)[-1]

    supported = {"mp3": "mp3", "wav": "wav", "flac": "flac", "ogg": "ogg", "m4a": "mp4", "mp4": "mp4"}
    if ext not in supported:
        return None
    return supported[ext], ext


async def _consume_quota_or_update_status(job_id: str, file_bytes: bytes, file_ext: str | None) -> bool:
    try:
        job = await transcription_table_service.get_by_job_id(job_id)
        if not job or not job.get("chat_id"):
            print(
                "QUOTA_CHECK_SKIPPED",
                {
                    "job_id": job_id,
                    "source": "drive",
                    "file_ext": file_ext,
                    "reason": "missing_job_chat_id",
                },
            )
            return True

        result = await quota_service.try_consume_monthly_bytes(
            str(job["chat_id"]),
            len(file_bytes),
        )
        if result.allowed:
            print(
                "QUOTA_BYTES_ACCEPTED",
                {
                    "job_id": job_id,
                    "chat_id": str(job["chat_id"]),
                    "source": "drive",
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
                "job_id": job_id,
                "chat_id": str(job["chat_id"]),
                "source": "drive",
                "file_ext": file_ext,
                "bytes": len(file_bytes),
                "used_bytes": result.used_bytes,
                "limit_bytes": result.limit_bytes,
                "quota_policy_version": result.quota_policy_version,
            },
        )
        await _replace_status(job_id, quota_formatting.format_quota_exceeded(result))
        return False
    except Exception as exc:
        print(
            "QUOTA_CHECK_ERROR",
            {
                "job_id": job_id,
                "source": "drive",
                "file_ext": file_ext,
                "error": repr(exc),
            },
        )
        return True


async def _append_status(job_id: str, message: str) -> None:
    job = await transcription_table_service.get_by_job_id(job_id)
    if not job:
        return

    chat_id = job.get("chat_id")
    message_id = job.get("status_message_id")
    if not chat_id or not message_id:
        return

    status_log = (job.get("status_log") or "").strip()
    new_log = f"{status_log}\n{message}" if status_log else message
    if not transcription_table_service.update_status_log(job_id, new_log):
        return

    try:
        await telegram_service.edit_message_text(int(chat_id), int(message_id), new_log)
    except Exception as exc:
        print("STATUS_EDIT_ERROR:", repr(exc))


async def _replace_status(job_id: str, message: str) -> None:
    job = await transcription_table_service.get_by_job_id(job_id)
    if not job:
        return

    chat_id = job.get("chat_id")
    message_id = job.get("status_message_id")
    if not chat_id or not message_id:
        return

    if not transcription_table_service.update_status_log(job_id, message):
        return

    try:
        await telegram_service.edit_message_text(int(chat_id), int(message_id), message)
    except Exception as exc:
        print("STATUS_REPLACE_ERROR:", repr(exc))
