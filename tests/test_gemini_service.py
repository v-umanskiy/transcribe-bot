import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest


class _FakeModels:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error

    def generate_content(self, **_kwargs):
        if self._error:
            raise self._error
        return self._response


class _FakeClient:
    def __init__(self, response=None, error=None):
        self.models = _FakeModels(response=response, error=error)


def _install_fake_google(monkeypatch, client):
    google_module = ModuleType("google")
    genai_module = ModuleType("google.genai")
    genai_module.Client = lambda **_kwargs: client
    genai_module.types = SimpleNamespace(GenerateContentConfig=lambda **kwargs: kwargs)
    google_module.genai = genai_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)


def _load_gemini_service(monkeypatch, client):
    import services

    secret_service_module = ModuleType("services.secret_service")
    secret_service_module.get_secret = lambda _: "dummy"
    monkeypatch.setitem(sys.modules, "services.secret_service", secret_service_module)
    monkeypatch.setattr(services, "secret_service", secret_service_module, raising=False)
    _install_fake_google(monkeypatch, client)
    sys.modules.pop("services.gemini_service", None)
    return importlib.import_module("services.gemini_service")


@pytest.mark.anyio
async def test_refine_text_returns_problem_when_gemini_response_has_no_text(monkeypatch):
    gemini_service = _load_gemini_service(
        monkeypatch,
        _FakeClient(response=SimpleNamespace(text=None, prompt_feedback="blocked", candidates=[])),
    )

    result = await gemini_service.refine_text("raw transcript")

    assert result.text == "raw transcript"
    assert result.language == "und"
    assert result.problem_reason == "gemini_empty_response"


@pytest.mark.anyio
async def test_refine_text_returns_problem_when_gemini_call_fails(monkeypatch):
    gemini_service = _load_gemini_service(
        monkeypatch,
        _FakeClient(error=TypeError("the JSON object must be str, bytes or bytearray, not NoneType")),
    )

    result = await gemini_service.refine_text("raw transcript")

    assert result.text == "raw transcript"
    assert result.language == "und"
    assert result.problem_reason == "gemini_call_error"


@pytest.mark.anyio
async def test_refine_text_reads_model_problem_reason(monkeypatch):
    gemini_service = _load_gemini_service(
        monkeypatch,
        _FakeClient(
            response=SimpleNamespace(
                text='{"refined_text":"Raw transcript.","language":"en","problem_reason":"unclear_transcript"}'
            )
        ),
    )

    result = await gemini_service.refine_text("raw transcript")

    assert result.text == "Raw transcript."
    assert result.language == "en"
    assert result.problem_reason == "unclear_transcript"
