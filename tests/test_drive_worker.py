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
async def test_record_usage_observe_records_drive_downloaded_bytes(drive_worker, monkeypatch):
    calls = []

    async def get_job(job_id):
        assert job_id == "job-1"
        return {"chat_id": "123"}

    async def record(chat_id, bytes_count, **kwargs):
        calls.append((chat_id, bytes_count, kwargs))

    monkeypatch.setattr(drive_worker.transcription_table_service, "get_by_job_id", get_job)
    monkeypatch.setattr(drive_worker.quota_service, "record_monthly_bytes", record)

    await drive_worker._record_usage_observe("job-1", b"abcd", "mp3")

    assert calls == [("123", 4, {"source": "drive", "file_ext": "mp3"})]


@pytest.mark.anyio
async def test_record_usage_observe_skips_drive_usage_without_chat_id(drive_worker, monkeypatch):
    calls = []

    async def get_job(_job_id):
        return None

    async def record(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(drive_worker.transcription_table_service, "get_by_job_id", get_job)
    monkeypatch.setattr(drive_worker.quota_service, "record_monthly_bytes", record)

    await drive_worker._record_usage_observe("job-1", b"abcd", "mp3")

    assert calls == []


@pytest.mark.anyio
async def test_record_usage_observe_does_not_block_drive_on_error(drive_worker, monkeypatch):
    async def get_job(_job_id):
        return {"chat_id": "123"}

    async def record(*_args, **_kwargs):
        raise RuntimeError("usage table unavailable")

    monkeypatch.setattr(drive_worker.transcription_table_service, "get_by_job_id", get_job)
    monkeypatch.setattr(drive_worker.quota_service, "record_monthly_bytes", record)

    await drive_worker._record_usage_observe("job-1", b"abcd", "mp3")
