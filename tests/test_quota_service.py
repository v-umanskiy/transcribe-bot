import re

import pytest

from services import quota_service


def test_current_month_uses_year_month_format():
    assert re.fullmatch(r"\d{4}-\d{2}", quota_service.current_month())


@pytest.mark.anyio
async def test_get_monthly_quota_status_defaults_when_no_usage(monkeypatch):
    async def get_usage(chat_id, month):
        assert chat_id == "123"
        assert month == "2026-06"
        return None

    monkeypatch.setattr(quota_service.usage_repository, "get_monthly_usage", get_usage)

    status = await quota_service.get_monthly_quota_status("123", month="2026-06")

    assert status.used_bytes == 0
    assert status.job_count == 0
    assert status.limit_bytes == quota_service.MONTHLY_QUOTA_BYTES
    assert status.quota_label == quota_service.MONTHLY_QUOTA_LABEL


@pytest.mark.anyio
async def test_get_monthly_quota_status_uses_persisted_usage(monkeypatch):
    async def get_usage(chat_id, month):
        assert chat_id == "123"
        assert month == "2026-06"
        return {
            "used_bytes": 25,
            "job_count": 2,
            "limit_bytes": 100,
            "quota_label": "persisted-label",
        }

    monkeypatch.setattr(quota_service.usage_repository, "get_monthly_usage", get_usage)

    status = await quota_service.get_monthly_quota_status("123", month="2026-06")

    assert status.used_bytes == 25
    assert status.job_count == 2
    assert status.limit_bytes == 100
    assert status.quota_label == "persisted-label"


@pytest.mark.anyio
async def test_get_current_quota_label_uses_current_status(monkeypatch):
    async def get_usage(chat_id, month):
        assert chat_id == "123"
        return {
            "used_bytes": 25,
            "job_count": 2,
            "limit_bytes": 100,
            "quota_label": "persisted-label",
        }

    monkeypatch.setattr(quota_service.usage_repository, "get_monthly_usage", get_usage)

    assert await quota_service.get_current_quota_label("123") == "persisted-label"


@pytest.mark.anyio
async def test_record_monthly_bytes_reports_updated_usage(monkeypatch):
    async def record(chat_id, month, bytes_count, limit_bytes, quota_label):
        assert chat_id == "123"
        assert month == "2026-06"
        assert bytes_count == 10
        assert limit_bytes == quota_service.MONTHLY_QUOTA_BYTES
        assert quota_label == quota_service.MONTHLY_QUOTA_LABEL
        return {
            "used_bytes": 40,
            "job_count": 3,
            "limit_bytes": limit_bytes,
            "quota_label": quota_label,
        }

    monkeypatch.setattr(quota_service.usage_repository, "record_monthly_bytes", record)

    result = await quota_service.record_monthly_bytes(
        123,
        10,
        month="2026-06",
        source="telegram",
        file_ext="ogg",
    )

    assert result.chat_id == "123"
    assert result.month == "2026-06"
    assert result.limit_bytes == quota_service.MONTHLY_QUOTA_BYTES
    assert result.quota_label == quota_service.MONTHLY_QUOTA_LABEL
    assert result.used_bytes == 40
    assert result.recorded_bytes == 10
    assert result.job_count == 3


@pytest.mark.anyio
async def test_try_consume_monthly_bytes_allows_and_reports_updated_usage(monkeypatch):
    async def consume(chat_id, month, bytes_count, limit_bytes, quota_label):
        assert chat_id == "123"
        assert month == "2026-06"
        assert bytes_count == 10
        assert limit_bytes == 100
        assert quota_label == "test-label"
        return {"used_bytes": 40, "limit_bytes": 100, "quota_label": "test-label"}

    async def get_usage(chat_id, month):
        assert chat_id == "123"
        assert month == "2026-06"
        return None

    monkeypatch.setattr(quota_service.usage_repository, "try_consume_monthly_bytes", consume)
    monkeypatch.setattr(quota_service.usage_repository, "get_monthly_usage", get_usage)

    result = await quota_service.try_consume_monthly_bytes(
        123,
        10,
        month="2026-06",
        limit_bytes=100,
        quota_label="test-label",
    )

    assert result.allowed is True
    assert result.limit_bytes == 100
    assert result.quota_label == "test-label"
    assert result.used_bytes == 40
    assert result.remaining_bytes == 60
    assert result.requested_bytes == 10


@pytest.mark.anyio
async def test_try_consume_monthly_bytes_uses_existing_persisted_limit(monkeypatch):
    async def get_usage(chat_id, month):
        assert chat_id == "123"
        assert month == "2026-06"
        return {"used_bytes": 40, "limit_bytes": 200, "quota_label": "existing-label"}

    async def consume(chat_id, month, bytes_count, limit_bytes, quota_label):
        assert chat_id == "123"
        assert month == "2026-06"
        assert bytes_count == 10
        assert limit_bytes == 200
        assert quota_label == "existing-label"
        return {"used_bytes": 50, "limit_bytes": 200, "quota_label": "existing-label"}

    monkeypatch.setattr(quota_service.usage_repository, "get_monthly_usage", get_usage)
    monkeypatch.setattr(quota_service.usage_repository, "try_consume_monthly_bytes", consume)

    result = await quota_service.try_consume_monthly_bytes(
        "123",
        10,
        month="2026-06",
        limit_bytes=100,
        quota_label="new-label",
    )

    assert result.allowed is True
    assert result.limit_bytes == 200
    assert result.quota_label == "existing-label"
    assert result.used_bytes == 50
    assert result.remaining_bytes == 150


@pytest.mark.anyio
async def test_try_consume_monthly_bytes_rejects_and_reports_current_usage(monkeypatch):
    async def consume(*_args):
        return None

    async def get_usage(chat_id, month):
        assert chat_id == "123"
        assert month == "2026-06"
        return {"used_bytes": 95, "limit_bytes": 100, "quota_label": "test-label"}

    monkeypatch.setattr(quota_service.usage_repository, "try_consume_monthly_bytes", consume)
    monkeypatch.setattr(quota_service.usage_repository, "get_monthly_usage", get_usage)

    result = await quota_service.try_consume_monthly_bytes(
        "123",
        10,
        month="2026-06",
        limit_bytes=100,
        quota_label="test-label",
    )

    assert result.allowed is False
    assert result.limit_bytes == 100
    assert result.quota_label == "test-label"
    assert result.used_bytes == 95
    assert result.remaining_bytes == 5
    assert result.requested_bytes == 10
