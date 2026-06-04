import importlib
import sys

import pytest

from services import secret_service


@pytest.fixture()
def drive_worker(monkeypatch):
    monkeypatch.setattr(secret_service, "get_secret", lambda _: "dummy")
    sys.modules.pop("services.telegram_service", None)
    sys.modules.pop("drive_worker", None)
    return importlib.import_module("drive_worker")


@pytest.mark.anyio
async def test_consume_quota_allows_drive_downloaded_bytes(drive_worker, monkeypatch):
    calls = []

    async def get_job(job_id):
        assert job_id == "job-1"
        return {"chat_id": "123"}

    async def consume(chat_id, bytes_count):
        calls.append((chat_id, bytes_count))
        return drive_worker.quota_service.MonthlyQuotaResult(
            allowed=True,
            chat_id=chat_id,
            month="2026-06",
            limit_bytes=100,
            quota_label="test-label",
            used_bytes=40,
            requested_bytes=bytes_count,
        )

    monkeypatch.setattr(drive_worker.transcription_table_service, "get_by_job_id", get_job)
    monkeypatch.setattr(drive_worker.quota_service, "try_consume_monthly_bytes", consume)

    assert await drive_worker._consume_quota_or_update_status("job-1", b"abcd", "mp3") is True

    assert calls == [("123", 4)]


@pytest.mark.anyio
async def test_consume_quota_skips_drive_usage_without_chat_id(drive_worker, monkeypatch):
    calls = []

    async def get_job(_job_id):
        return None

    async def consume(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(drive_worker.transcription_table_service, "get_by_job_id", get_job)
    monkeypatch.setattr(drive_worker.quota_service, "try_consume_monthly_bytes", consume)

    assert await drive_worker._consume_quota_or_update_status("job-1", b"abcd", "mp3") is True

    assert calls == []


@pytest.mark.anyio
async def test_consume_quota_does_not_block_drive_on_error(drive_worker, monkeypatch):
    async def get_job(_job_id):
        return {"chat_id": "123"}

    async def consume(*_args, **_kwargs):
        raise RuntimeError("usage table unavailable")

    monkeypatch.setattr(drive_worker.transcription_table_service, "get_by_job_id", get_job)
    monkeypatch.setattr(drive_worker.quota_service, "try_consume_monthly_bytes", consume)

    assert await drive_worker._consume_quota_or_update_status("job-1", b"abcd", "mp3") is True


@pytest.mark.anyio
async def test_consume_quota_rejects_drive_downloaded_bytes(drive_worker, monkeypatch):
    statuses = []

    async def get_job(_job_id):
        return {"chat_id": "123"}

    async def consume(chat_id, bytes_count):
        return drive_worker.quota_service.MonthlyQuotaResult(
            allowed=False,
            chat_id=chat_id,
            month="2026-06",
            limit_bytes=100,
            quota_label="test-label",
            used_bytes=95,
            requested_bytes=bytes_count,
        )

    async def replace_status(job_id, message):
        statuses.append((job_id, message))

    monkeypatch.setattr(drive_worker.transcription_table_service, "get_by_job_id", get_job)
    monkeypatch.setattr(drive_worker.quota_service, "try_consume_monthly_bytes", consume)
    monkeypatch.setattr(drive_worker, "_replace_status", replace_status)

    assert await drive_worker._consume_quota_or_update_status("job-1", b"abcd", "mp3") is False
    assert statuses == [
        (
            "job-1",
            "Monthly limit reached.\n\n"
            "Used: 0.0 MB / 0.0 MB\n"
            "This file: 0.0 MB\n"
            "Remaining: 0.0 MB\n\n"
            "Your quota resets next month.",
        )
    ]


@pytest.mark.anyio
async def test_replace_status_overwrites_status_log_and_message(drive_worker, monkeypatch):
    updates = []
    edits = []

    async def get_job(job_id):
        assert job_id == "job-1"
        return {"chat_id": "123", "status_message_id": "456", "status_log": "Old status"}

    async def edit_message_text(chat_id, message_id, message):
        edits.append((chat_id, message_id, message))

    monkeypatch.setattr(drive_worker.transcription_table_service, "get_by_job_id", get_job)
    monkeypatch.setattr(
        drive_worker.transcription_table_service,
        "update_status_log",
        lambda job_id, message: updates.append((job_id, message)) or True,
    )
    monkeypatch.setattr(drive_worker.telegram_service, "edit_message_text", edit_message_text)

    await drive_worker._replace_status("job-1", "New status")

    assert updates == [("job-1", "New status")]
    assert edits == [(123, 456, "New status")]
