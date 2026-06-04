import time
from repository import transcription_repository
from utils.constants import RETENTION_DAYS


async def save_transcription_job(
    chat_id: int,
    job_id: str,
    file_url: str | None,
    file_key: str | None,
    status_message_id: int | None,
    status_log: str | None,
    source_url: str | None = None,
):
    ttl = int(time.time()) + RETENTION_DAYS * 24 * 60 * 60
    item = {
        "chat_id": str(chat_id),
        "ts": int(time.time() * 1000),
        "job_id": job_id,
        "status": "pending",
        "status_message_id": status_message_id,
        "status_log": status_log or "",
        "ttl": ttl,
    }
    if file_url:
        item["file_url"] = file_url
    if file_key:
        item["file_key"] = file_key
    if source_url:
        item["source_url"] = source_url
    return await transcription_repository.put_job(item)


async def get_by_job_id(job_id: str) -> dict | None:
    try:
        item = await transcription_repository.get_job_by_id(job_id)
        if not item:
            print(f"No transcription found for job_id={job_id}")
            return None
        return item
    except Exception as exc:
        print(f"Error getting transcription {job_id}: {exc}")
        return None


def mark_job_done(job_id: str) -> bool:
    try:
        return transcription_repository.update_status_if_pending(job_id, "done")
    except Exception as exc:
        print(f"Failed to mark job {job_id} as done: {exc}")
        return False


def update_status_log(job_id: str, status_log: str) -> bool:
    try:
        return transcription_repository.update_status_log(job_id, status_log)
    except Exception as exc:
        print(f"Failed to update status log for job {job_id}: {exc}")
        return False


def update_job_file_info(job_id: str, file_url: str, file_key: str) -> bool:
    try:
        return transcription_repository.update_job_file_info(job_id, file_url, file_key)
    except Exception as exc:
        print(f"Failed to update job file info for job {job_id}: {exc}")
        return False
