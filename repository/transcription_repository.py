import asyncio
import os
import boto3


dynamodb = boto3.resource("dynamodb")
transcriptions_table = dynamodb.Table(os.getenv("TRANSCRIPTIONS_TABLE_NAME"))


async def put_job(item: dict):
    return await asyncio.to_thread(transcriptions_table.put_item, Item=item)


async def get_job_by_id(job_id: str) -> dict | None:
    def _get():
        resp = transcriptions_table.get_item(Key={"job_id": job_id})
        return resp.get("Item")

    return await asyncio.to_thread(_get)


def update_status_if_pending(job_id: str, new_status: str) -> bool:
    try:
        transcriptions_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #s = :new_status",
            ConditionExpression="#s = :pending",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":new_status": new_status, ":pending": "pending"},
            ReturnValues="UPDATED_NEW",
        )
        return True
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return False
