# Transcribe Bot

Telegram bot for transcribing voice notes and audio files. Short clips are handled via OpenAI Whisper, longer files are sent to AWS Transcribe, and the results are refined with Google Gemini before replying back in Telegram.

## Features
- Accepts Telegram voice messages, audio files, and public Google Drive links.
- Uses Whisper for short clips; AWS Transcribe for longer ones.
- Splits large transcripts into chunks and refines them with Gemini.
- Delivers results back to Telegram in multiple parts when needed.

## Architecture
- `app.py` provides FastAPI endpoints for Telegram webhooks.
- `transcript_event_entry.py` handles transcript S3 events (EventBridge -> Lambda).
- `worker.py` handles transcript chunk refinement and delivery (SQS-triggered Lambda).
- `drive_worker.py` downloads public Drive files and kicks off AWS Transcribe.
- DynamoDB tables store transcription jobs and chunk state.
- S3 stores uploaded audio and transcript JSONs.

## API Endpoints
- `GET /` health check.
- `POST /telegram/webhook` Telegram webhook receiver (uses `WEBHOOK_SECRET`).

## Configuration

### Environment variables
- `S3_BUCKET_NAME` S3 bucket for audio and transcripts.
- `SQS_QUEUE_URL` SQS queue for transcript chunks.
- `SQS_DRIVE_QUEUE_URL` SQS queue for Drive downloads.
- `GEMINI_MODEL` optional override for Gemini model (default `gemini-2.5-flash`).
- `SECRET_NAME` AWS Secrets Manager name (default `transcribe-bot-secret`).

### Secrets (AWS Secrets Manager)
- `TELEGRAM_BOT_TOKEN` Telegram bot token.
- `WEBHOOK_SECRET` Telegram webhook secret token.
- `GEMINI_API_KEY` Gemini API key.
- `OPENAI_API_KEY` OpenAI API key for Whisper.

## Local Development
1. Install dependencies: `pip install -r requirements.txt`.
2. Install a server runner (for example): `pip install uvicorn`.
3. Start the API: `uvicorn app:app --reload`.
4. Expose the endpoint (ngrok, etc.) and register the Telegram webhook.

## Deploy
The deployment script builds and ships Lambda artifacts:
- API Lambda: `./deploy.sh prod`
- Chunk worker: `./deploy.sh prod worker`
- Drive worker: `./deploy.sh prod drive`
- Transcript event lambda: `./deploy.sh prod transcript`

`deploy.sh` uses the AWS CLI profile `personal` and supports `S3_BUCKET` for artifacts.

## Tests
Run tests with: `pytest`.
