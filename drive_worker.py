import asyncio
import json

from services import google_drive_service
from services import s3_service
from services import transcription_aws_service
from services import transcription_table_service


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

        file_bytes, file_name, file_id = await google_drive_service.download_public_file(url)
        if not file_bytes or not file_name or not file_id:
            print("DRIVE_DOWNLOAD_FAILED:", url)
            continue

        drive_info = _extract_drive_file_info(file_name)
        if drive_info is None:
            print("DRIVE_UNSUPPORTED_FILE:", file_name)
            continue

        media_format, file_ext = drive_info
        file_key = f"audiofiles/drive-{file_id}.{file_ext}"

        file_url, _ = await s3_service.upload_file_to_s3(file_bytes, file_key)
        if not file_url:
            print("S3_UPLOAD_FAILED:", file_key)
            continue

        transcription_table_service.update_job_file_info(job_id, file_url, file_key)
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
