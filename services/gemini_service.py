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
    problem_reason: str | None = None


def format_problem_message(problem_reason: str) -> str:
    return f"Refinement issue: {problem_reason}.\nSending the best available transcript."


async def refine_text(text: str) -> RefinementResult:
    text_len = len(text or "")
    print(f"GEMINI_REFINE_START chars={text_len}")

    def _call() -> RefinementResult:
        try:
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
                            "problem_reason": {
                                "type": "STRING",
                                "description": (
                                    "Empty string when refinement succeeded. If the transcript cannot "
                                    "be refined, provide a short and informative reason (5 words max)."
                                    "E.g.: 'inappropriate content', 'unreadable text'."
                                ),
                            },
                        },
                        "required": ["refined_text", "language", "problem_reason"],
                    },
                ),
            )
        except Exception as exc:
            print(f"GEMINI_REFINE_CALL_ERROR chars={text_len} error={repr(exc)}")
            return RefinementResult(
                text=text or "",
                language="und",
                problem_reason="gemini_call_error",
            )

        response_text = getattr(response, "text", None)
        if response_text is None:
            print(
                "GEMINI_REFINE_EMPTY_RESPONSE",
                {
                    "chars": text_len,
                    "prompt_feedback": repr(getattr(response, "prompt_feedback", None)),
                    "candidates": repr(getattr(response, "candidates", None)),
                },
            )
            return RefinementResult(
                text=text or "",
                language="und",
                problem_reason="gemini_empty_response",
            )

        try:
            payload = json.loads(response_text or "{}")
        except (TypeError, json.JSONDecodeError) as exc:
            print(
                "GEMINI_REFINE_PARSE_ERROR",
                {
                    "chars": text_len,
                    "error": repr(exc),
                    "response_text_preview": str(response_text)[:500],
                },
            )
            return RefinementResult(
                text=text or "",
                language="und",
                problem_reason="gemini_parse_error",
            )

        return RefinementResult(
            text=str(payload.get("refined_text") or ""),
            language=str(payload.get("language") or "und").lower(),
            problem_reason=str(payload.get("problem_reason") or "").strip() or None,
        )

    result = await asyncio.to_thread(_call)
    print(
        f"GEMINI_REFINE_DONE chars_in={text_len} chars_out={len(result.text)} "
        f"language={result.language} problem_reason={result.problem_reason or ''}"
    )
    return result
