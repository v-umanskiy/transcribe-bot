import asyncio
import os
import time

import boto3


dynamodb = boto3.resource("dynamodb")
usage_table = dynamodb.Table(os.getenv("USAGE_TABLE_NAME", "transcribe_bot_usage_prod"))


async def get_monthly_usage(chat_id: str, month: str) -> dict | None:
    def _get():
        resp = usage_table.get_item(Key={"chat_id": str(chat_id), "month": month})
        return resp.get("Item")

    return await asyncio.to_thread(_get)


async def try_consume_monthly_bytes(
    chat_id: str,
    month: str,
    bytes_count: int,
    limit_bytes: int,
) -> dict | None:
    if bytes_count < 0:
        raise ValueError("bytes_count must be non-negative")
    if limit_bytes < 0:
        raise ValueError("limit_bytes must be non-negative")

    now = int(time.time())
    remaining_before_update = limit_bytes - bytes_count
    if remaining_before_update < 0:
        return None

    def _update():
        try:
            resp = usage_table.update_item(
                Key={"chat_id": str(chat_id), "month": month},
                UpdateExpression=(
                    "SET #updated_at = :now, #created_at = if_not_exists(#created_at, :now) "
                    "ADD #used_bytes :bytes_count, #job_count :one"
                ),
                ConditionExpression="attribute_not_exists(#used_bytes) OR #used_bytes <= :remaining",
                ExpressionAttributeNames={
                    "#created_at": "created_at",
                    "#updated_at": "updated_at",
                    "#used_bytes": "used_bytes",
                    "#job_count": "job_count",
                },
                ExpressionAttributeValues={
                    ":now": now,
                    ":bytes_count": int(bytes_count),
                    ":remaining": int(remaining_before_update),
                    ":one": 1,
                },
                ReturnValues="ALL_NEW",
            )
            return resp.get("Attributes")
        except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            return None

    return await asyncio.to_thread(_update)
