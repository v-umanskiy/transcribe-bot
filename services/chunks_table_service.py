import time

from repository import chunks_repository
from utils.constants import RETENTION_DAYS


async def save_chunk(job_id: str, chunk_index: int, total_chunks: int, text: str, chat_id: str):
    created_at = int(time.time())
    ttl = created_at + RETENTION_DAYS * 24 * 60 * 60
    item = {
        "job_id": job_id,
        "chunk_index": int(chunk_index),
        "total_chunks": int(total_chunks),
        "text": text,
        "chat_id": str(chat_id),
        "status": "pending",
        "created_at": created_at,
        "ttl": ttl,
    }
    return await chunks_repository.put_chunk(item)


async def get_chunk(job_id: str, chunk_index: int) -> dict | None:
    return await chunks_repository.get_chunk(job_id, chunk_index)


def mark_chunk_done(job_id: str, chunk_index: int, language: str) -> bool:
    return chunks_repository.mark_chunk_done(job_id, chunk_index, language)
