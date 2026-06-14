import importlib
import sys

import pytest

from services import secret_service
from utils.constants import LIMIT_LOAD_FAILED_MESSAGE, START_MESSAGE_TEMPLATE


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
async def test_consume_quota_allows_downloaded_bytes(webhook_service, monkeypatch):
    calls = []

    async def consume(chat_id, bytes_count):
        calls.append((chat_id, bytes_count))
        return webhook_service.quota_service.MonthlyQuotaResult(
            allowed=True,
            chat_id=chat_id,
            month="2026-06",
            limit_bytes=100,
            quota_label="test-label",
            used_bytes=40,
            requested_bytes=bytes_count,
        )

    monkeypatch.setattr(webhook_service.quota_service, "try_consume_monthly_bytes", consume)

    assert await webhook_service._consume_quota_or_notify(123, b"abc", "ogg") is True
    assert calls == [("123", 3)]


@pytest.mark.anyio
async def test_consume_quota_rejects_downloaded_bytes(webhook_service, monkeypatch):
    sent_messages = []

    async def consume(chat_id, bytes_count):
        return webhook_service.quota_service.MonthlyQuotaResult(
            allowed=False,
            chat_id=chat_id,
            month="2026-06",
            limit_bytes=100,
            quota_label="test-label",
            used_bytes=95,
            requested_bytes=bytes_count,
        )

    async def send_message(chat_id, message):
        sent_messages.append((chat_id, message))

    monkeypatch.setattr(webhook_service.quota_service, "try_consume_monthly_bytes", consume)
    monkeypatch.setattr(webhook_service.telegram_service, "send_message", send_message)

    assert await webhook_service._consume_quota_or_notify(123, b"abcdef", "ogg") is False
    assert sent_messages == [
        (
            123,
            "Monthly limit reached.\n\n"
            "Used: 0.0 MB / 0.0 MB\n"
            "This file: 0.0 MB\n"
            "Remaining: 0.0 MB\n\n"
            "Your quota resets next month.",
        )
    ]


@pytest.mark.anyio
async def test_consume_quota_fails_open_on_error(webhook_service, monkeypatch):
    async def consume(*_args, **_kwargs):
        raise RuntimeError("usage table unavailable")

    monkeypatch.setattr(webhook_service.quota_service, "try_consume_monthly_bytes", consume)

    assert await webhook_service._consume_quota_or_notify(123, b"abc", "ogg") is True


@pytest.mark.anyio
async def test_handle_command_ignores_non_commands(webhook_service):
    assert await webhook_service._handle_command(123, "hello") is None


@pytest.mark.anyio
async def test_start_command_sends_intro(webhook_service, monkeypatch):
    sent_messages = []

    async def send_message(chat_id, message):
        sent_messages.append((chat_id, message))

    monkeypatch.setattr(webhook_service.telegram_service, "send_message", send_message)

    result = await webhook_service._handle_telegram_webhook_data(
        {"message": {"chat": {"id": 123}, "text": "/start"}}
    )

    assert result == {"ok": True}
    assert sent_messages == [
        (
            123,
            START_MESSAGE_TEMPLATE,
        )
    ]


@pytest.mark.anyio
async def test_limit_command_sends_quota_status(webhook_service, monkeypatch):
    sent_messages = []

    async def get_status(chat_id):
        assert chat_id == "123"
        return webhook_service.quota_service.MonthlyQuotaStatus(
            chat_id=chat_id,
            month="2026-06",
            limit_bytes=100 * 1024 * 1024,
            quota_label="test-label",
            used_bytes=25 * 1024 * 1024,
            job_count=3,
        )

    async def send_message(chat_id, message):
        sent_messages.append((chat_id, message))

    monkeypatch.setattr(webhook_service.quota_service, "get_monthly_quota_status", get_status)
    monkeypatch.setattr(webhook_service.telegram_service, "send_message", send_message)

    result = await webhook_service._handle_telegram_webhook_data(
        {"message": {"chat": {"id": 123}, "text": "/limit"}}
    )

    assert result == {"ok": True}
    assert sent_messages == [
        (
            123,
            "Monthly usage for June 2026\n\n"
            "Used: 25.0 MB\n"
            "Limit: 100.0 MB\n"
            "Remaining: 75.0 MB\n"
            "Files processed: 3",
        )
    ]


@pytest.mark.anyio
async def test_limit_command_error_is_non_blocking(webhook_service, monkeypatch):
    sent_messages = []

    async def get_status(_chat_id):
        raise RuntimeError("usage table unavailable")

    async def send_message(chat_id, message):
        sent_messages.append((chat_id, message))

    monkeypatch.setattr(webhook_service.quota_service, "get_monthly_quota_status", get_status)
    monkeypatch.setattr(webhook_service.telegram_service, "send_message", send_message)

    result = await webhook_service._handle_telegram_webhook_data(
        {"message": {"chat": {"id": 123}, "text": "/limit"}}
    )

    assert result == {"ok": True}
    assert sent_messages == [
        (123, LIMIT_LOAD_FAILED_MESSAGE)
    ]
