import asyncio
import os
import boto3


dynamodb = boto3.resource("dynamodb")
transcriptions_table = dynamodb.Table(os.getenv("TRANSCRIPTIONS_TABLE_NAME"))


async def put_job(item: dict):
    return await asyncio.to_thread(transcriptions_table.put_item, Item=item)
