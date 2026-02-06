import asyncio
import json

from services import chunks_table_service
from services import telegram_service


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

        job_id = payload.get("job_id")
        chunk_index = payload.get("chunk_index")
        if not job_id or chunk_index is None:
            print("SQS_BODY_MISSING_FIELDS:", payload)
            continue

        chunk = await chunks_table_service.get_chunk(job_id, int(chunk_index))
        if not chunk:
            print("CHUNK_NOT_FOUND:", job_id, chunk_index)
            continue

        if chunk.get("status") != "pending":
            print("CHUNK_ALREADY_DONE:", job_id, chunk_index)
            continue

        chat_id = chunk.get("chat_id")
        text = chunk.get("text")
        total_chunks = int(chunk.get("total_chunks") or 1)
        if not chat_id or not text:
            print("CHUNK_MISSING_DATA:", job_id, chunk_index)
            continue

        if total_chunks > 1:
            text = f"Part {chunk_index}\\n\\n{text}"

        await telegram_service.send_message(int(chat_id), text)

        if not chunks_table_service.mark_chunk_done(job_id, int(chunk_index)):
            print("CHUNK_MARK_DONE_FAILED:", job_id, chunk_index)
