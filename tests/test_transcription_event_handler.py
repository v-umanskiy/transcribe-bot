import importlib
import sys

import pytest

from services import secret_service


@pytest.fixture()
def transcription_event_handler(monkeypatch):
    monkeypatch.setattr(secret_service, "get_secret", lambda _: "dummy")
    sys.modules.pop("services.telegram_service", None)
    sys.modules.pop("services.transcription_event_handler", None)
    return importlib.import_module("services.transcription_event_handler")


@pytest.mark.anyio
async def test_process_transcript_text_empty_chunks(transcription_event_handler, monkeypatch):
    monkeypatch.setattr(
        transcription_event_handler.text_utils,
        "split_into_chunks",
        lambda *_args, **_kwargs: [],
    )

    result = await transcription_event_handler._process_transcript_text(
        job_id="job-1",
        transcription_job={"job_id": "job-1"},
        chat_id="123",
        transcript_text="",
    )

    assert result == {"status": "empty_transcript"}


@pytest.mark.anyio
async def test_process_transcript_text_single_chunk(transcription_event_handler, monkeypatch):
    monkeypatch.setattr(
        transcription_event_handler.text_utils,
        "split_into_chunks",
        lambda *_args, **_kwargs: ["hi"],
    )

    saved_chunks = []
    update_calls = []
    mark_done = []
    sent_chunks = []

    async def save_chunk(job_id, idx, total, chunk, chat_id):
        saved_chunks.append((job_id, idx, total, chunk, chat_id))

    async def update_status(job, total_chunks):
        update_calls.append((job, total_chunks))

    monkeypatch.setattr(transcription_event_handler.chunks_table_service, "save_chunk", save_chunk)
    monkeypatch.setattr(transcription_event_handler, "_update_status_after_transcript", update_status)
    monkeypatch.setattr(
        transcription_event_handler.transcription_table_service,
        "get_by_job_id",
        lambda *_: (_ for _ in ()).throw(AssertionError("get_by_job_id should not be called")),
    )
    monkeypatch.setattr(
        transcription_event_handler.transcription_table_service,
        "mark_job_done",
        lambda job_id: mark_done.append(job_id),
    )
    monkeypatch.setattr(
        transcription_event_handler.sqs_service,
        "send_chunk",
        lambda job_id, idx: sent_chunks.append((job_id, idx)),
    )

    job = {"job_id": "job-2"}
    result = await transcription_event_handler._process_transcript_text(
        job_id="job-2",
        transcription_job=job,
        chat_id="123",
        transcript_text="hi",
    )

    assert result == {"status": "ok"}
    assert saved_chunks == [("job-2", 1, 1, "hi", "123")]
    assert update_calls == [(job, 1)]
    assert mark_done == ["job-2"]
    assert sent_chunks == [("job-2", 1)]


@pytest.mark.anyio
async def test_process_transcript_text_multiple_chunks(transcription_event_handler, monkeypatch):
    monkeypatch.setattr(
        transcription_event_handler.text_utils,
        "split_into_chunks",
        lambda *_args, **_kwargs: ["a", "b", "c"],
    )

    saved_chunks = []
    update_calls = []
    mark_done = []
    sent_chunks = []

    async def save_chunk(job_id, idx, total, chunk, chat_id):
        saved_chunks.append((job_id, idx, total, chunk, chat_id))

    async def update_status(job, total_chunks):
        update_calls.append((job, total_chunks))

    async def get_by_job_id(job_id):
        return {"job_id": job_id}

    monkeypatch.setattr(transcription_event_handler.chunks_table_service, "save_chunk", save_chunk)
    monkeypatch.setattr(transcription_event_handler, "_update_status_after_transcript", update_status)
    monkeypatch.setattr(
        transcription_event_handler.transcription_table_service,
        "get_by_job_id",
        get_by_job_id,
    )
    monkeypatch.setattr(
        transcription_event_handler.transcription_table_service,
        "mark_job_done",
        lambda job_id: mark_done.append(job_id),
    )
    monkeypatch.setattr(
        transcription_event_handler.sqs_service,
        "send_chunk",
        lambda job_id, idx: sent_chunks.append((job_id, idx)),
    )

    result = await transcription_event_handler._process_transcript_text(
        job_id="job-3",
        transcription_job=None,
        chat_id="123",
        transcript_text="abc",
    )

    assert result == {"status": "ok"}
    assert saved_chunks == [
        ("job-3", 1, 3, "a", "123"),
        ("job-3", 2, 3, "b", "123"),
        ("job-3", 3, 3, "c", "123"),
    ]
    assert update_calls == [({"job_id": "job-3"}, 3)]
    assert mark_done == ["job-3"]
    assert sent_chunks == [("job-3", 1)]
