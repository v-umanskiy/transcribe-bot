import pytest

from services import chunks_table_service
from utils.constants import RETENTION_DAYS


@pytest.mark.anyio
async def test_save_chunk_stores_created_at_and_ttl(monkeypatch):
    saved_items = []
    now = 1_781_431_200

    monkeypatch.setattr(chunks_table_service.time, "time", lambda: now)

    async def put_chunk(item):
        saved_items.append(item)
        return {"ok": True}

    monkeypatch.setattr(chunks_table_service.chunks_repository, "put_chunk", put_chunk)

    result = await chunks_table_service.save_chunk("job-1", 1, 2, "Hallo", "123")

    assert result == {"ok": True}
    assert saved_items == [
        {
            "job_id": "job-1",
            "chunk_index": 1,
            "total_chunks": 2,
            "text": "Hallo",
            "chat_id": "123",
            "status": "pending",
            "created_at": now,
            "ttl": now + RETENTION_DAYS * 24 * 60 * 60,
        }
    ]
