from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal

import usage_report


def test_month_timestamp_bounds():
    start, end = usage_report.month_timestamp_bounds("2026-06")

    assert datetime.fromtimestamp(start, UTC) == datetime(2026, 6, 1, tzinfo=UTC)
    assert datetime.fromtimestamp(end, UTC) == datetime(2026, 7, 1, tzinfo=UTC)


def test_month_timestamp_bounds_crosses_year():
    start, end = usage_report.month_timestamp_bounds("2026-12")

    assert datetime.fromtimestamp(start, UTC) == datetime(2026, 12, 1, tzinfo=UTC)
    assert datetime.fromtimestamp(end, UTC) == datetime(2027, 1, 1, tzinfo=UTC)


def test_build_language_counts_groups_by_chat_id():
    counts = usage_report.build_language_counts(
        [
            {"chat_id": "123", "language": "RU"},
            {"chat_id": "123", "language": "ru"},
            {"chat_id": "123", "language": "de"},
            {"chat_id": "456", "language": "en"},
            {"chat_id": "456"},
        ]
    )

    assert counts == {
        "123": Counter({"ru": 2, "de": 1}),
        "456": Counter({"en": 1}),
    }


def test_build_rows_includes_languages():
    items = [
        {
            "chat_id": "123",
            "username": "victor",
            "used_bytes": Decimal(10 * usage_report.BYTES_PER_MB),
            "limit_bytes": Decimal(30 * usage_report.BYTES_PER_MB),
            "job_count": Decimal(2),
            "updated_at": Decimal(1_781_431_200),
        }
    ]

    rows = usage_report.build_rows(items, {"123": Counter({"ru": 3, "de": 1})})

    assert rows[0][7] == "ru: 3, de: 1"
