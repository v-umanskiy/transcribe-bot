from dataclasses import dataclass

from utils import quota_formatting


@dataclass(frozen=True)
class _Status:
    month: str
    limit_bytes: int
    used_bytes: int
    remaining_bytes: int
    job_count: int


@dataclass(frozen=True)
class _Result:
    limit_bytes: int
    used_bytes: int
    requested_bytes: int
    remaining_bytes: int


def test_format_bytes_mb():
    assert quota_formatting.format_bytes_mb(0) == "0 MB"
    assert quota_formatting.format_bytes_mb(512 * 1024) == "0.5 MB"
    assert quota_formatting.format_bytes_mb(10 * 1024 * 1024) == "10 MB"


def test_format_quota_status():
    status = _Status(
        month="2026-06",
        limit_bytes=100 * 1024 * 1024,
        used_bytes=25 * 1024 * 1024,
        remaining_bytes=75 * 1024 * 1024,
        job_count=3,
    )

    assert quota_formatting.format_quota_status(status) == (
        "Monthly usage for June 2026\n\n"
        "Used: 25 MB\n"
        "Limit: 100 MB\n"
        "Remaining: 75 MB\n"
        "Files processed: 3"
    )


def test_format_quota_exceeded():
    result = _Result(
        limit_bytes=100 * 1024 * 1024,
        used_bytes=95 * 1024 * 1024,
        requested_bytes=10 * 1024 * 1024,
        remaining_bytes=5 * 1024 * 1024,
    )

    assert quota_formatting.format_quota_exceeded(result) == (
        "Monthly limit reached.\n\n"
        "Used: 95 MB / 100 MB\n"
        "This file: 10 MB\n"
        "Remaining: 5.0 MB\n\n"
        "Your quota resets next month."
    )
