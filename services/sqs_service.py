import json
import os
import boto3

sqs_client = boto3.client("sqs")
QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")


def send_chunk(job_id: str, chunk_index: int) -> None:
    if not QUEUE_URL:
        raise RuntimeError("SQS_QUEUE_URL not set")

    payload = {
        "job_id": job_id,
        "chunk_index": int(chunk_index),
    }
    sqs_client.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(payload),
    )
