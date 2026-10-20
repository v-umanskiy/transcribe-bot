import importlib
import sys
from dataclasses import dataclass
from types import ModuleType

import pytest


@pytest.fixture()
def worker(monkeypatch):
    import services

    @dataclass(frozen=True)
    class RefinementResult:
        text: str
        language: str
        problem_reason: str | None = None

    fake_modules = {
        "services.chunks_table_service": ModuleType("services.chunks_table_service"),
        "services.sqs_service": ModuleType("services.sqs_service"),
        "services.gemini_service": ModuleType("services.gemini_service"),
        "services.telegram_service": ModuleType("services.telegram_service"),
        "services.transcription_table_service": ModuleType(
            "services.transcription_table_service"
        ),
    }
    fake_modules["services.gemini_service"].RefinementResult = RefinementResult
    fake_modules["services.gemini_service"].refine_text = None
    fake_modules["services.gemini_service"].format_problem_message = (
        lambda reason: f"Refinement issue: {reason}.\nSending the best available transcript."
    )
    fake_modules["services.chunks_table_service"].get_chunk = None
    fake_modules["services.chunks_table_service"].mark_chunk_done = None
    fake_modules["services.sqs_service"].send_chunk = None
    fake_modules["services.telegram_service"].send_message = None
    fake_modules["services.telegram_service"].delete_message = None
    fake_modules["services.transcription_table_service"].get_by_job_id = None

    for module_name, module in fake_modules.items():
        monkeypatch.setitem(sys.modules, module_name, module)
        monkeypatch.setattr(services, module_name.rsplit(".", 1)[1], module, raising=False)

    sys.modules.pop("worker", None)
    return importlib.import_module("worker")


def test_worker_log_does_not_contain_message_bodies(worker, capsys):
    event = {"Records": [{"body": "secret, not json"}, {"body": '{"note": "secret value"}'}]}

    worker.handler(event, None)

    logged = capsys.readouterr().out
    assert "SQS_BODY_INVALID_JSON" in logged
    assert "SQS_BODY_MISSING_FIELDS" in logged
    assert "'note'" in logged
    assert "secret" not in logged


@pytest.mark.anyio
async def test_worker_sends_problem_reason_and_continues_chunk_chain(worker, monkeypatch):
    sent_messages = []
    marked_done = []
    sent_chunks = []

    async def get_chunk(job_id, chunk_index):
        assert (job_id, chunk_index) == ("job-1", 1)
        return {
            "chat_id": "123",
            "text": "raw transcript",
            "total_chunks": 2,
            "status": "pending",
        }

    async def refine_text(text):
        assert text == "raw transcript"
        return worker.gemini_service.RefinementResult(
            text="unsafe refined transcript",
            language="und",
            problem_reason="gemini_empty_response",
        )

    async def send_message(chat_id, message):
        sent_messages.append((chat_id, message))

    monkeypatch.setattr(worker.chunks_table_service, "get_chunk", get_chunk)
    monkeypatch.setattr(worker.gemini_service, "refine_text", refine_text)
    monkeypatch.setattr(worker.telegram_service, "send_message", send_message)
    monkeypatch.setattr(
        worker.chunks_table_service,
        "mark_chunk_done",
        lambda job_id, chunk_index, language: marked_done.append(
            (job_id, chunk_index, language)
        )
        or True,
    )
    monkeypatch.setattr(
        worker.sqs_service,
        "send_chunk",
        lambda job_id, chunk_index: sent_chunks.append((job_id, chunk_index)),
    )

    await worker._handle_records(
        [{"body": '{"job_id":"job-1","chunk_index":1}'}]
    )

    assert sent_messages == [
        (
            123,
            "Refinement issue: gemini_empty_response.\n"
            "Sending the best available transcript.",
        ),
        (123, "Part 1/2\n\nraw transcript"),
    ]
    assert marked_done == [("job-1", 1, "und")]
    assert sent_chunks == [("job-1", 2)]
