import asyncio

from services import transcription_event_handler


def handler(event, _context):
    print("TRANSCRIPT_EVENT:", event)
    asyncio.run(transcription_event_handler.handle_transcription_data(event))
    return {"ok": True}
