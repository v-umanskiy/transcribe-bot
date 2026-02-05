from repository import chunks_repository


async def save_chunk(job_id: str, chunk_index: int, total_chunks: int, text: str, chat_id: str):
    item = {
        "job_id": job_id,
        "chunk_index": int(chunk_index),
        "total_chunks": int(total_chunks),
        "text": text,
        "chat_id": str(chat_id),
        "status": "pending",
    }
    return await chunks_repository.put_chunk(item)
