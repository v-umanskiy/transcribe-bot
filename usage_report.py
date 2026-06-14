#!/usr/bin/env python3

import argparse
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, ProfileNotFound


DEFAULT_TABLE_NAME = "transcribe_bot_usage_prod"
DEFAULT_REGION = "eu-west-1"
BYTES_PER_MB = 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show monthly transcription-bot usage.")
    parser.add_argument(
        "month",
        nargs="?",
        default=datetime.now(UTC).strftime("%Y-%m"),
        help="Month in YYYY-MM format. Defaults to the current UTC month.",
    )
    parser.add_argument(
        "--table",
        default=os.getenv("USAGE_TABLE_NAME", DEFAULT_TABLE_NAME),
        help=f"DynamoDB table name. Defaults to {DEFAULT_TABLE_NAME}.",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION", DEFAULT_REGION),
        help=f"AWS region. Defaults to {DEFAULT_REGION}.",
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("AWS_PROFILE"),
        help="Optional AWS CLI profile name.",
    )
    args = parser.parse_args()
    try:
        datetime.strptime(args.month, "%Y-%m")
    except ValueError:
        parser.error("month must use YYYY-MM format")
    return args


def load_usage(table, month: str) -> list[dict]:
    items = []
    request = {
        "FilterExpression": Attr("month").eq(month),
        "ProjectionExpression": (
            "#chat_id, #month, #username, #used_bytes, #limit_bytes, "
            "#job_count, #updated_at"
        ),
        "ExpressionAttributeNames": {
            "#chat_id": "chat_id",
            "#month": "month",
            "#username": "username",
            "#used_bytes": "used_bytes",
            "#limit_bytes": "limit_bytes",
            "#job_count": "job_count",
            "#updated_at": "updated_at",
        },
    }
    while True:
        response = table.scan(**request)
        items.extend(response.get("Items") or [])
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        request["ExclusiveStartKey"] = last_key


def as_int(value) -> int:
    if isinstance(value, Decimal):
        return int(value)
    return int(value or 0)


def format_mb(bytes_count: int) -> str:
    return f"{bytes_count / BYTES_PER_MB:.1f} MB"


def format_updated_at(timestamp: int) -> str:
    if not timestamp:
        return "-"
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d")


def build_rows(items: list[dict]) -> list[list[str]]:
    rows = []
    sorted_items = sorted(items, key=lambda item: as_int(item.get("used_bytes")), reverse=True)
    for item in sorted_items:
        used_bytes = as_int(item.get("used_bytes"))
        limit_bytes = as_int(item.get("limit_bytes"))
        remaining_bytes = max(limit_bytes - used_bytes, 0)
        usage_percent = used_bytes * 100 / limit_bytes if limit_bytes else 0
        username = str(item.get("username") or "-")
        rows.append(
            [
                f"@{username}" if username != "-" else username,
                str(item.get("chat_id") or "-"),
                format_mb(used_bytes),
                format_mb(limit_bytes),
                format_mb(remaining_bytes),
                str(as_int(item.get("job_count"))),
                f"{usage_percent:.0f}%",
                format_updated_at(as_int(item.get("updated_at"))),
            ]
        )
    return rows


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    ]
    numeric_columns = {2, 3, 4, 5, 6}

    def render_row(row: list[str]) -> str:
        cells = []
        for index, value in enumerate(row):
            cells.append(value.rjust(widths[index]) if index in numeric_columns else value.ljust(widths[index]))
        return "  ".join(cells)

    divider = "  ".join("-" * width for width in widths)
    return "\n".join([render_row(headers), divider, *(render_row(row) for row in rows)])


def main() -> int:
    args = parse_args()
    try:
        session = boto3.Session(profile_name=args.profile, region_name=args.region)
        table = session.resource("dynamodb").Table(args.table)
        items = load_usage(table, args.month)
    except ProfileNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except NoCredentialsError:
        print("AWS credentials not found. Configure them or pass --profile PROFILE.", file=sys.stderr)
        return 1
    except (BotoCoreError, ClientError) as exc:
        print(f"Could not read {args.table}: {exc}", file=sys.stderr)
        return 1

    rows = build_rows(items)
    print(f"Transcription bot usage for {args.month} ({args.table}, {args.region})\n")
    if not rows:
        print("No usage rows found.")
        return 0

    headers = ["Username", "Chat ID", "Used", "Limit", "Remaining", "Files", "Usage", "Updated"]
    print(render_table(headers, rows))

    total_used = sum(as_int(item.get("used_bytes")) for item in items)
    total_files = sum(as_int(item.get("job_count")) for item in items)
    print(f"\nUsers: {len(items)}  Files: {total_files}  Used: {format_mb(total_used)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
