import asyncio
import json
import os
from dataclasses import dataclass

from google import genai

from utils.constants import REFINE_SYSTEM_PROMPT
from . import secret_service

_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_CLIENT = genai.Client(api_key=secret_service.get_secret("GEMINI_API_KEY"))


@dataclass(frozen=True)
class RefinementResult:
    text: str
    language: str


async def refine_text(text: str) -> RefinementResult:
    text_len = len(text or "")
    print(f"GEMINI_REFINE_START chars={text_len}")

    def _call() -> RefinementResult:
        response = _CLIENT.models.generate_content(
            model=_MODEL_NAME,
            contents=[{"role": "user", "parts": [{"text": text or ""}]}],
            config=genai.types.GenerateContentConfig(
                system_instruction=REFINE_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "refined_text": {"type": "STRING"},
                        "language": {
                            "type": "STRING",
                            "description": (
                                "Dominant language of the input as an ISO 639-1 two-letter code, "
                                "or 'und' if it cannot be determined."
                            ),
                        },
                    },
                    "required": ["refined_text", "language"],
                },
            ),
        )
        payload = json.loads(response.text or "{}")
        return RefinementResult(
            text=str(payload.get("refined_text") or ""),
            language=str(payload.get("language") or "und").lower(),
        )

    result = await asyncio.to_thread(_call)
    print(
        f"GEMINI_REFINE_DONE chars_in={text_len} chars_out={len(result.text)} "
        f"language={result.language}"
    )
    return result
