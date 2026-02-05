import asyncio
import os

from google import genai

from utils.constants import REFINE_PROMPT_TEMPLATE
from . import secret_service

_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_CLIENT = genai.Client(api_key=secret_service.get_secret("GEMINI_API_KEY"))


async def refine_text(text: str) -> str:
    prompt = REFINE_PROMPT_TEMPLATE + (text or "")
    text_len = len(text or "")
    print(f"GEMINI_REFINE_START chars={text_len}")

    def _call() -> str:
        response = _CLIENT.models.generate_content(
            model=_MODEL_NAME,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
        )
        return response.text or ""

    result = await asyncio.to_thread(_call)
    print(f"GEMINI_REFINE_DONE chars_in={text_len} chars_out={len(result)}")
    return result
