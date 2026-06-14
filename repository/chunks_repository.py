import asyncio
import boto3


dynamodb = boto3.resource("dynamodb")
chunks_table = dynamodb.Table("transcribe_bot_chunks_prod")


async def put_chunk(item: dict):
    return await asyncio.to_thread(chunks_table.put_item, Item=item)


async def get_chunk(job_id: str, chunk_index: int) -> dict | None:
    def _get():
        resp = chunks_table.get_item(Key={"job_id": job_id, "chunk_index": int(chunk_index)})
        return resp.get("Item")

    return await asyncio.to_thread(_get)


def mark_chunk_done(job_id: str, chunk_index: int, language: str) -> bool:
    try:
        chunks_table.update_item(
            Key={"job_id": job_id, "chunk_index": int(chunk_index)},
            UpdateExpression="SET #s = :done, #l = :language",
            ConditionExpression="#s = :pending",
            ExpressionAttributeNames={"#s": "status", "#l": "language"},
            ExpressionAttributeValues={
                ":done": "done",
                ":pending": "pending",
                ":language": language,
            },
            ReturnValues="UPDATED_NEW",
        )
        return True
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return False
