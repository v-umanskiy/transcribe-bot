import asyncio
import json
import os
from dataclasses import dataclass

from google import genai
from pydantic import BaseModel, Field

from utils.constants import REFINE_SYSTEM_PROMPT
from . import secret_service

_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_CLIENT = genai.Client(api_key=secret_service.get_secret("GEMINI_API_KEY"))


@dataclass(frozen=True)
class RefinementResult:
    text: str
    language: str
    problem_reason: str | None = None


class _RefinementPayload(BaseModel):
    refined_text: str = Field(
        description="The refined transcription as plain text with no formatting."
    )
    language: str = Field(
        description=(
            "Dominant language of the input as an ISO 639-1 two-letter code, "
            "or 'und' if it cannot be determined."
        )
    )
    problem_reason: str = Field(
        default="",
        description=(
            "Empty string when refinement succeeded. If the transcript cannot "
            "be refined, provide a short and informative reason (5 words max). "
            "E.g.: 'inappropriate content', 'unreadable text'."
        ),
    )


def format_problem_message(problem_reason: str) -> str:
    return f"Refinement issue: {problem_reason}.\nSending the best available transcript."


def _get_attr_or_key(value, name: str):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _reason_label(value) -> str:
    raw = getattr(value, "value", None) or getattr(value, "name", None) or str(value)
    return str(raw).split(".")[-1].lower()


def _empty_response_reason(response) -> str:
    prompt_feedback = getattr(response, "prompt_feedback", None)
    block_reason = _get_attr_or_key(prompt_feedback, "block_reason")
    if block_reason:
        return f"prompt_blocked:{_reason_label(block_reason)}"

    candidates = getattr(response, "candidates", None) or []
    if candidates:
        finish_reason = _get_attr_or_key(candidates[0], "finish_reason")
        label = _reason_label(finish_reason) if finish_reason else ""
        if label and label not in {"stop", "finish_reason_unspecified"}:
            return f"candidate_stopped:{label}"

    return "gemini_empty_response"


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
                    response_schema=_RefinementPayload,
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
                {"chars": text_len, "reason": _empty_response_reason(response)},
            )
            return RefinementResult(
                text=text or "",
                language="und",
                problem_reason=_empty_response_reason(response),
            )

        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, _RefinementPayload):
            return RefinementResult(
                text=parsed.refined_text,
                language=(parsed.language or "und").lower(),
                problem_reason=(parsed.problem_reason or "").strip() or None,
            )

        try:
            payload = json.loads(response_text or "{}")
        except (TypeError, json.JSONDecodeError) as exc:
            print(
                "GEMINI_REFINE_PARSE_ERROR",
                {"chars": text_len, "error": repr(exc), "response_chars": len(str(response_text))},
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
