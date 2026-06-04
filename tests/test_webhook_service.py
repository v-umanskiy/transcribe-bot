import importlib
import sys

import pytest

from services import secret_service


class _DummySecretsManager:
    def get_secret_value(self, SecretId: str) -> dict:
        return {"SecretString": "{}"}


@pytest.fixture()
def webhook_service(monkeypatch):
    monkeypatch.setattr(secret_service, "sm", _DummySecretsManager())
    monkeypatch.setattr(secret_service, "_secrets_payload", {})
    monkeypatch.setattr(secret_service, "get_secret", lambda _: "dummy")
    sys.modules.pop("services.telegram_service", None)
    sys.modules.pop("services.webhook_service", None)
    sys.modules.pop("services.gemini_service", None)
    return importlib.import_module("services.webhook_service")


def test_should_use_whisper_rejects_missing_duration(webhook_service):
    assert webhook_service._should_use_whisper(None, None, "mp3") is False


def test_should_use_whisper_rejects_long_duration(webhook_service):
    assert webhook_service._should_use_whisper(181, None, "mp3") is False


def test_should_use_whisper_rejects_unsupported_extension(webhook_service):
    assert webhook_service._should_use_whisper(30, None, "m4a") is False


def test_should_use_whisper_accepts_small_supported_file(webhook_service):
    assert webhook_service._should_use_whisper(30, 20 * 1024 * 1024, "mp3") is True


def test_should_use_whisper_rejects_large_file(webhook_service):
    assert webhook_service._should_use_whisper(30, 20 * 1024 * 1024 + 1, "mp3") is False


def test_should_use_whisper_accepts_missing_size_with_supported_ext(webhook_service):
    assert webhook_service._should_use_whisper(30, None, ".WAV") is True


@pytest.mark.anyio
async def test_record_usage_observe_records_downloaded_bytes(webhook_service, monkeypatch):
    calls = []

    async def record(chat_id, bytes_count, **kwargs):
        calls.append((chat_id, bytes_count, kwargs))

    monkeypatch.setattr(webhook_service.quota_service, "record_monthly_bytes", record)

    await webhook_service._record_usage_observe(123, b"abc", "ogg")

    assert calls == [("123", 3, {"source": "telegram", "file_ext": "ogg"})]


@pytest.mark.anyio
async def test_record_usage_observe_does_not_block_on_error(webhook_service, monkeypatch):
    async def record(*_args, **_kwargs):
        raise RuntimeError("usage table unavailable")

    monkeypatch.setattr(webhook_service.quota_service, "record_monthly_bytes", record)

    await webhook_service._record_usage_observe(123, b"abc", "ogg")
