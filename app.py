from fastapi import FastAPI, Header, HTTPException, Request
from mangum import Mangum

import services.secret_service as secret_service
import services.webhook_service as webhook_service

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
    print("TELEGRAM_UPDATE_RECEIVED", {"update_id": data.get("update_id") if isinstance(data, dict) else None})

    return await webhook_service.handle_telegram_webhook_data(data)

