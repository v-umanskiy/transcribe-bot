import os
from dataclasses import dataclass
from datetime import UTC, datetime

from repository import usage_repository
from utils.constants import MONTHLY_QUOTA_BYTES


@dataclass(frozen=True)
class MonthlyQuotaResult:
    allowed: bool
    chat_id: str
    month: str
    limit_bytes: int
    used_bytes: int
    requested_bytes: int

    @property
    def remaining_bytes(self) -> int:
        return max(self.limit_bytes - self.used_bytes, 0)


def current_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


async def get_monthly_usage(chat_id: str, month: str | None = None) -> dict | None:
    return await usage_repository.get_monthly_usage(str(chat_id), month or current_month())


async def try_consume_monthly_bytes(
    chat_id: str,
    bytes_count: int,
    *,
    month: str | None = None,
    limit_bytes: int | None = None,
) -> MonthlyQuotaResult:
    usage_month = month or current_month()
    resolved_limit_bytes = int(
        limit_bytes
        if limit_bytes is not None
        else os.getenv("MONTHLY_QUOTA_BYTES", MONTHLY_QUOTA_BYTES)
    )
    updated = await usage_repository.try_consume_monthly_bytes(
        str(chat_id),
        usage_month,
        int(bytes_count),
        resolved_limit_bytes,
    )
    if updated:
        return MonthlyQuotaResult(
            allowed=True,
            chat_id=str(chat_id),
            month=usage_month,
            limit_bytes=resolved_limit_bytes,
            used_bytes=int(updated.get("used_bytes") or 0),
            requested_bytes=int(bytes_count),
        )

    usage = await usage_repository.get_monthly_usage(str(chat_id), usage_month)
    return MonthlyQuotaResult(
        allowed=False,
        chat_id=str(chat_id),
        month=usage_month,
        limit_bytes=resolved_limit_bytes,
        used_bytes=int((usage or {}).get("used_bytes") or 0),
        requested_bytes=int(bytes_count),
    )
