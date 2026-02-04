import os
import asyncio
import mimetypes
import boto3

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

s3_client = boto3.client("s3")


async def upload_file_to_s3(file_bytes: bytes, file_id: str) -> tuple[str | None, str | None]:
    if not S3_BUCKET_NAME:
        print("S3_BUCKET_NAME not set. Cannot upload file.")
        return None, None

    mime_type, _ = mimetypes.guess_type(file_id)
    if not mime_type:
        mime_type = "application/octet-stream"

    try:
        key = f"telegram-files/{file_id}"
        await asyncio.to_thread(
            s3_client.put_object,
            Bucket=S3_BUCKET_NAME,
            Key=key,
            Body=file_bytes,
            ContentType=mime_type,
        )
        return f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{key}", key
    except Exception as exc:
        print(f"S3 upload error: {repr(exc)}")
        return None, None
