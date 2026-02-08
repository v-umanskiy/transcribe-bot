from . import s3_service
import json
from . import transcription_table_service
from . import chunks_table_service
from urllib.parse import unquote_plus
from utils import text_utils
from . import sqs_service
from . import telegram_service


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

    await telegram_service.edit_message_text(int(chat_id), int(message_id), new_log)