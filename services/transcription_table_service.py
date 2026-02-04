import time
from repository import transcription_repository


async def save_transcription_job(chat_id: int, job_id: str, file_url: str, file_key: str):
    item = {
        "chat_id": str(chat_id),
        "ts": int(time.time() * 1000),
        "job_id": job_id,
        "file_url": file_url,
        "file_key": file_key,
        "status": "pending",
    }
    return await transcription_repository.put_job(item)
