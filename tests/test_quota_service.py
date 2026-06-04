import re

import pytest

from services import quota_service


def test_current_month_uses_year_month_format():
    assert re.fullmatch(r"\d{4}-\d{2}", quota_service.current_month())


@pytest.mark.anyio
async def test_try_consume_monthly_bytes_allows_and_reports_updated_usage(monkeypatch):
    async def consume(chat_id, month, bytes_count, limit_bytes):
        assert chat_id == "123"
        assert month == "2026-06"
        assert bytes_count == 10
        assert limit_bytes == 100
        return {"used_bytes": 40}

    async def get_usage(*_args):
        raise AssertionError("get_monthly_usage should not be called on success")

    monkeypatch.setattr(quota_service.usage_repository, "try_consume_monthly_bytes", consume)
    monkeypatch.setattr(quota_service.usage_repository, "get_monthly_usage", get_usage)

    result = await quota_service.try_consume_monthly_bytes(
        123,
        10,
        month="2026-06",
        limit_bytes=100,
    )

    assert result.allowed is True
    assert result.used_bytes == 40
    assert result.remaining_bytes == 60
    assert result.requested_bytes == 10


@pytest.mark.anyio
async def test_try_consume_monthly_bytes_rejects_and_reports_current_usage(monkeypatch):
    async def consume(*_args):
        return None

    async def get_usage(chat_id, month):
        assert chat_id == "123"
        assert month == "2026-06"
        return {"used_bytes": 95}

    monkeypatch.setattr(quota_service.usage_repository, "try_consume_monthly_bytes", consume)
    monkeypatch.setattr(quota_service.usage_repository, "get_monthly_usage", get_usage)

    result = await quota_service.try_consume_monthly_bytes(
        "123",
        10,
        month="2026-06",
        limit_bytes=100,
    )

    assert result.allowed is False
    assert result.used_bytes == 95
    assert result.remaining_bytes == 5
    assert result.requested_bytes == 10
