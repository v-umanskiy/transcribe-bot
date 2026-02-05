import asyncio
import boto3


dynamodb = boto3.resource("dynamodb")
chunks_table = dynamodb.Table("transcribe_bot_chunks_prod")


async def put_chunk(item: dict):
    return await asyncio.to_thread(chunks_table.put_item, Item=item)
