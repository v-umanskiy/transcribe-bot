import asyncio
import json

from services import chunks_table_service
from services import sqs_service
from services import gemini_service
from utils import text_utils
from services import telegram_service
from services import transcription_table_service


def handler(event, _context):
    print("SQS_EVENT_RECEIVED", {"records": len(event.get("Records") or [])})

    asyncio.run(_handle_records(event.get("Records") or []))
    return {"ok": True}


async def _handle_records(records: list[dict]):
    for record in records:
        body = record.get("body") or ""
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            print("SQS_BODY_INVALID_JSON", {"chars": len(body)})
            continue

        job_id = payload.get("job_id")
        chunk_index = payload.get("chunk_index")
        if not job_id or chunk_index is None:
            print("SQS_BODY_MISSING_FIELDS", {"keys": sorted(payload)})
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

        refinement = await gemini_service.refine_text(text)
        refined = text if refinement.problem_reason else (refinement.text.strip() or text)

        if refinement.problem_reason:
            await telegram_service.send_message(
                int(chat_id),
                gemini_service.format_problem_message(refinement.problem_reason),
            )

        parts = text_utils.split_by_length(refined, max_len=3500)

        if total_chunks > 1:
            parts[0] = f"Part {chunk_index}/{total_chunks}\n\n{parts[0]}"

        for part in parts:
            await telegram_service.send_message(int(chat_id), part)

        if not chunks_table_service.mark_chunk_done(
            job_id,
            int(chunk_index),
            refinement.language,
        ):
            print("CHUNK_MARK_DONE_FAILED:", job_id, chunk_index)
            continue

        if int(chunk_index) < total_chunks:
            sqs_service.send_chunk(job_id, int(chunk_index) + 1)
            continue

        job = await transcription_table_service.get_by_job_id(job_id)
        if job:
            status_message_id = job.get("status_message_id")
            if status_message_id:
                await telegram_service.delete_message(int(chat_id), int(status_message_id))
