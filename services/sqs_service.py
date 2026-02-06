import json
import os
import boto3

sqs_client = boto3.client("sqs")
QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")
DRIVE_QUEUE_URL = os.getenv("SQS_DRIVE_QUEUE_URL", "")


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


def send_drive_download(job_id: str, url: str) -> None:
    if not DRIVE_QUEUE_URL:
        raise RuntimeError("SQS_DRIVE_QUEUE_URL not set")

    payload = {
        "type": "drive",
        "job_id": job_id,
        "url": url,
    }
    sqs_client.send_message(
        QueueUrl=DRIVE_QUEUE_URL,
        MessageBody=json.dumps(payload),
    )
