from dataclasses import dataclass

from utils import quota_formatting


@dataclass(frozen=True)
class _Status:
    month: str
    limit_bytes: int
    used_bytes: int
    remaining_bytes: int
    job_count: int


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
