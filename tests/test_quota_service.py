import re

import pytest

from services import quota_service


def test_current_month_uses_year_month_format():
    assert re.fullmatch(r"\d{4}-\d{2}", quota_service.current_month())


@pytest.mark.anyio
async def test_record_monthly_bytes_reports_updated_usage(monkeypatch):
    async def record(chat_id, month, bytes_count, limit_bytes, quota_policy_version):
        assert chat_id == "123"
        assert month == "2026-06"
        assert bytes_count == 10
        assert limit_bytes == quota_service.MONTHLY_QUOTA_BYTES
        assert quota_policy_version == quota_service.MONTHLY_QUOTA_POLICY_VERSION
        return {
            "used_bytes": 40,
            "job_count": 3,
            "limit_bytes": limit_bytes,
            "quota_policy_version": quota_policy_version,
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
    assert result.quota_policy_version == quota_service.MONTHLY_QUOTA_POLICY_VERSION
    assert result.used_bytes == 40
    assert result.recorded_bytes == 10
    assert result.job_count == 3


@pytest.mark.anyio
async def test_try_consume_monthly_bytes_allows_and_reports_updated_usage(monkeypatch):
    async def consume(chat_id, month, bytes_count, limit_bytes, quota_policy_version):
        assert chat_id == "123"
        assert month == "2026-06"
        assert bytes_count == 10
        assert limit_bytes == 100
        assert quota_policy_version == "test-policy"
        return {"used_bytes": 40, "limit_bytes": 100, "quota_policy_version": "test-policy"}

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
        quota_policy_version="test-policy",
    )

    assert result.allowed is True
    assert result.limit_bytes == 100
    assert result.quota_policy_version == "test-policy"
    assert result.used_bytes == 40
    assert result.remaining_bytes == 60
    assert result.requested_bytes == 10


@pytest.mark.anyio
async def test_try_consume_monthly_bytes_uses_existing_persisted_limit(monkeypatch):
    async def get_usage(chat_id, month):
        assert chat_id == "123"
        assert month == "2026-06"
        return {"used_bytes": 40, "limit_bytes": 200, "quota_policy_version": "existing-policy"}

    async def consume(chat_id, month, bytes_count, limit_bytes, quota_policy_version):
        assert chat_id == "123"
        assert month == "2026-06"
        assert bytes_count == 10
        assert limit_bytes == 200
        assert quota_policy_version == "existing-policy"
        return {"used_bytes": 50, "limit_bytes": 200, "quota_policy_version": "existing-policy"}

    monkeypatch.setattr(quota_service.usage_repository, "get_monthly_usage", get_usage)
    monkeypatch.setattr(quota_service.usage_repository, "try_consume_monthly_bytes", consume)

    result = await quota_service.try_consume_monthly_bytes(
        "123",
        10,
        month="2026-06",
        limit_bytes=100,
        quota_policy_version="new-policy",
    )

    assert result.allowed is True
    assert result.limit_bytes == 200
    assert result.quota_policy_version == "existing-policy"
    assert result.used_bytes == 50
    assert result.remaining_bytes == 150


@pytest.mark.anyio
async def test_try_consume_monthly_bytes_rejects_and_reports_current_usage(monkeypatch):
    async def consume(*_args):
        return None

    async def get_usage(chat_id, month):
        assert chat_id == "123"
        assert month == "2026-06"
        return {"used_bytes": 95, "limit_bytes": 100, "quota_policy_version": "test-policy"}

    monkeypatch.setattr(quota_service.usage_repository, "try_consume_monthly_bytes", consume)
    monkeypatch.setattr(quota_service.usage_repository, "get_monthly_usage", get_usage)

    result = await quota_service.try_consume_monthly_bytes(
        "123",
        10,
        month="2026-06",
        limit_bytes=100,
        quota_policy_version="test-policy",
    )

    assert result.allowed is False
    assert result.limit_bytes == 100
    assert result.quota_policy_version == "test-policy"
    assert result.used_bytes == 95
    assert result.remaining_bytes == 5
    assert result.requested_bytes == 10
