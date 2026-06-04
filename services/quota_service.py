import os
from dataclasses import dataclass
from datetime import UTC, datetime

from repository import usage_repository
from utils.constants import MONTHLY_QUOTA_BYTES, MONTHLY_QUOTA_POLICY_VERSION


@dataclass(frozen=True)
class MonthlyUsageRecord:
    chat_id: str
    month: str
    limit_bytes: int
    quota_policy_version: str
    used_bytes: int
    recorded_bytes: int
    job_count: int


@dataclass(frozen=True)
class MonthlyQuotaResult:
    allowed: bool
    chat_id: str
    month: str
    limit_bytes: int
    quota_policy_version: str
    used_bytes: int
    requested_bytes: int

    @property
    def remaining_bytes(self) -> int:
        return max(self.limit_bytes - self.used_bytes, 0)


@dataclass(frozen=True)
class MonthlyQuotaStatus:
    chat_id: str
    month: str
    limit_bytes: int
    quota_policy_version: str
    used_bytes: int
    job_count: int

    @property
    def remaining_bytes(self) -> int:
        return max(self.limit_bytes - self.used_bytes, 0)


def current_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def configured_limit_bytes() -> int:
    return int(os.getenv("MONTHLY_QUOTA_BYTES", MONTHLY_QUOTA_BYTES))


def configured_quota_policy_version() -> str:
    return os.getenv("MONTHLY_QUOTA_POLICY_VERSION", MONTHLY_QUOTA_POLICY_VERSION)


async def get_monthly_usage(chat_id: str, month: str | None = None) -> dict | None:
    return await usage_repository.get_monthly_usage(str(chat_id), month or current_month())


async def get_monthly_quota_status(chat_id: str, month: str | None = None) -> MonthlyQuotaStatus:
    usage_month = month or current_month()
    usage = await usage_repository.get_monthly_usage(str(chat_id), usage_month)
    return MonthlyQuotaStatus(
        chat_id=str(chat_id),
        month=usage_month,
        limit_bytes=int((usage or {}).get("limit_bytes") or configured_limit_bytes()),
        quota_policy_version=str(
            (usage or {}).get("quota_policy_version") or configured_quota_policy_version()
        ),
        used_bytes=int((usage or {}).get("used_bytes") or 0),
        job_count=int((usage or {}).get("job_count") or 0),
    )


async def record_monthly_bytes(
    chat_id: str,
    bytes_count: int,
    *,
    month: str | None = None,
    source: str | None = None,
    file_ext: str | None = None,
) -> MonthlyUsageRecord:
    usage_month = month or current_month()
    updated = await usage_repository.record_monthly_bytes(
        str(chat_id),
        usage_month,
        int(bytes_count),
        configured_limit_bytes(),
        configured_quota_policy_version(),
    )
    record = MonthlyUsageRecord(
        chat_id=str(chat_id),
        month=usage_month,
        limit_bytes=int(updated.get("limit_bytes") or 0),
        quota_policy_version=str(updated.get("quota_policy_version") or ""),
        used_bytes=int(updated.get("used_bytes") or 0),
        recorded_bytes=int(bytes_count),
        job_count=int(updated.get("job_count") or 0),
    )
    print(
        "USAGE_BYTES_RECORDED",
        {
            "chat_id": record.chat_id,
            "month": record.month,
            "bytes": record.recorded_bytes,
            "used_bytes": record.used_bytes,
            "job_count": record.job_count,
            "limit_bytes": record.limit_bytes,
            "quota_policy_version": record.quota_policy_version,
            "source": source,
            "file_ext": file_ext,
        },
    )
    return record


async def try_consume_monthly_bytes(
    chat_id: str,
    bytes_count: int,
    *,
    month: str | None = None,
    limit_bytes: int | None = None,
    quota_policy_version: str | None = None,
) -> MonthlyQuotaResult:
    usage_month = month or current_month()
    usage = await usage_repository.get_monthly_usage(str(chat_id), usage_month)
    resolved_limit_bytes = int(
        (usage or {}).get("limit_bytes")
        or (limit_bytes if limit_bytes is not None else configured_limit_bytes())
    )
    resolved_policy_version = str(
        (usage or {}).get("quota_policy_version")
        or quota_policy_version
        or configured_quota_policy_version()
    )
    updated = await usage_repository.try_consume_monthly_bytes(
        str(chat_id),
        usage_month,
        int(bytes_count),
        resolved_limit_bytes,
        resolved_policy_version,
    )
    if updated:
        return MonthlyQuotaResult(
            allowed=True,
            chat_id=str(chat_id),
            month=usage_month,
            limit_bytes=int(updated.get("limit_bytes") or resolved_limit_bytes),
            quota_policy_version=str(updated.get("quota_policy_version") or resolved_policy_version),
            used_bytes=int(updated.get("used_bytes") or 0),
            requested_bytes=int(bytes_count),
        )

    usage = usage or await usage_repository.get_monthly_usage(str(chat_id), usage_month)
    return MonthlyQuotaResult(
        allowed=False,
        chat_id=str(chat_id),
        month=usage_month,
        limit_bytes=int((usage or {}).get("limit_bytes") or resolved_limit_bytes),
        quota_policy_version=str((usage or {}).get("quota_policy_version") or resolved_policy_version),
        used_bytes=int((usage or {}).get("used_bytes") or 0),
        requested_bytes=int(bytes_count),
    )
