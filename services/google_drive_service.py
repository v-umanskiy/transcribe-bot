import mimetypes
import re
from typing import Tuple

import httpx


def extract_drive_file_id(url: str) -> str | None:
    if not url:
        return None

    patterns = [
        r"drive\.google\.com/file/d/([^/]+)",
        r"drive\.google\.com/open\?id=([^&]+)",
        r"drive\.google\.com/uc\?id=([^&]+)",
        r"docs\.google\.com/uc\?id=([^&]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


async def download_public_file(
    url: str,
    max_bytes: int | None = None,
) -> Tuple[bytes | None, str | None, str | None, str | None]:
    file_id = extract_drive_file_id(url)
    if not file_id:
        return None, None, None, "invalid_url"

    base_url = "https://drive.google.com/uc?export=download"
    async with httpx.AsyncClient(timeout=600, follow_redirects=True) as client:
        response = await client.get(base_url, params={"id": file_id})
        response.raise_for_status()

        token = _extract_confirm_token(response)
        if token:
            response = await client.get(base_url, params={"id": file_id, "confirm": token})
            response.raise_for_status()

        if _content_too_large(response, max_bytes):
            return None, None, file_id, "file_too_large"

        content = response.content
        if max_bytes is not None and len(content) > max_bytes:
            return None, None, file_id, "file_too_large"

        filename = _extract_filename(response.headers.get("content-disposition"), file_id, response.headers.get("content-type"))
        return content, filename, file_id, None


def _extract_confirm_token(response: httpx.Response) -> str | None:
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            return value

    if response.headers.get("content-type", "").startswith("text/html"):
        match = re.search(r"confirm=([0-9A-Za-z_]+)", response.text)
        if match:
            return match.group(1)
    return None


def _content_too_large(response: httpx.Response, max_bytes: int | None) -> bool:
    if max_bytes is None:
        return False
    content_length = response.headers.get("content-length")
    if not content_length:
        return False
    try:
        return int(content_length) > max_bytes
    except ValueError:
        return False


def _extract_filename(content_disposition: str | None, file_id: str, content_type: str | None) -> str:
    if content_disposition:
        match = re.search(r'filename="?([^";]+)"?', content_disposition)
        if match:
            return match.group(1)

    ext = None
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
    if not ext:
        ext = ".bin"
    return f"{file_id}{ext}"
