import os
import tempfile

from openai import OpenAI

from . import secret_service


def transcribe_audio_bytes(file_bytes: bytes, file_ext: str) -> str:
    api_key = secret_service.get_secret("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY in secret")

    suffix = f".{file_ext}" if file_ext and not file_ext.startswith(".") else file_ext
    if not suffix:
        suffix = ".wav"

    client = OpenAI(api_key=api_key)
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="json",
            )
        return transcription.get("text") if isinstance(transcription, dict) else transcription.text
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
