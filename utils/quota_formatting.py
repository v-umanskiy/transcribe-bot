from datetime import datetime
from typing import Protocol


class QuotaStatus(Protocol):
    month: str
    limit_bytes: int
    used_bytes: int
    remaining_bytes: int
    job_count: int


class QuotaResult(Protocol):
    limit_bytes: int
    used_bytes: int
    requested_bytes: int
    remaining_bytes: int


def format_bytes_mb(bytes_count: int) -> str:
    mb = bytes_count / (1024 * 1024)
    if mb == 0:
        return "0 MB"
    if mb >= 10:
        return f"{mb:.0f} MB"
    return f"{mb:.1f} MB"


def format_month(month: str) -> str:
    try:
        return datetime.strptime(month, "%Y-%m").strftime("%B %Y")
    except ValueError:
        return month


def format_quota_status(status: QuotaStatus) -> str:
    return (
        f"Monthly usage for {format_month(status.month)}\n\n"
        f"Used: {format_bytes_mb(status.used_bytes)}\n"
        f"Limit: {format_bytes_mb(status.limit_bytes)}\n"
        f"Remaining: {format_bytes_mb(status.remaining_bytes)}\n"
        f"Files processed: {status.job_count}"
    )


def format_quota_exceeded(result: QuotaResult) -> str:
    return (
        "Monthly limit reached.\n\n"
        f"Used: {format_bytes_mb(result.used_bytes)} / {format_bytes_mb(result.limit_bytes)}\n"
        f"This file: {format_bytes_mb(result.requested_bytes)}\n"
        f"Remaining: {format_bytes_mb(result.remaining_bytes)}\n\n"
        "Your quota resets next month."
    )
