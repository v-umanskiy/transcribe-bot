import asyncio
import boto3


dynamodb = boto3.resource("dynamodb")
transcriptions_table = dynamodb.Table("transcribe_bot_transcription_prod")


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


def update_status_log(job_id: str, status_log: str) -> bool:
    transcriptions_table.update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #l = :log",
        ExpressionAttributeNames={"#l": "status_log"},
        ExpressionAttributeValues={":log": status_log},
        ReturnValues="UPDATED_NEW",
    )
    return True
