from fastapi import FastAPI, Header, HTTPException, Request
from mangum import Mangum

import services.secret_service as secret_service
import services.webhook_service as webhook_service
import services.transcription_event_handler as transcription_event_handler

app = FastAPI()
handler = Mangum(app)

WEBHOOK_SECRET = secret_service.get_secret("WEBHOOK_SECRET")


@app.get("/")
def read_root():
    return {"ok": True}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Bad secret")

    data = await request.json()
    print("Incoming update:", data)

    return await webhook_service.handle_telegram_webhook_data(data)


@app.post("/transcript/event")
async def transcript_event(request: Request):
    event = await request.json()
    return await transcription_event_handler.handle_transcription_data(event)
