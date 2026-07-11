import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest


class _FakeModels:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
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


class _FakeBaseModel:
    def __init__(self, **kwargs):
        for name in getattr(self, "__annotations__", {}):
            setattr(self, name, kwargs.get(name, getattr(self.__class__, name, None)))


def _install_fake_pydantic(monkeypatch):
    pydantic_module = ModuleType("pydantic")
    pydantic_module.BaseModel = _FakeBaseModel
    pydantic_module.Field = lambda default=None, **_kwargs: default
    monkeypatch.setitem(sys.modules, "pydantic", pydantic_module)


def _load_gemini_service(monkeypatch, client):
    import services

    secret_service_module = ModuleType("services.secret_service")
    secret_service_module.get_secret = lambda _: "dummy"
    monkeypatch.setitem(sys.modules, "services.secret_service", secret_service_module)
    monkeypatch.setattr(services, "secret_service", secret_service_module, raising=False)
    _install_fake_google(monkeypatch, client)
    _install_fake_pydantic(monkeypatch)
    sys.modules.pop("services.gemini_service", None)
    return importlib.import_module("services.gemini_service")


@pytest.mark.anyio
async def test_refine_text_returns_problem_when_gemini_response_has_no_text(monkeypatch):
    gemini_service = _load_gemini_service(
        monkeypatch,
        _FakeClient(
            response=SimpleNamespace(
                text=None,
                prompt_feedback=SimpleNamespace(
                    block_reason=SimpleNamespace(value="PROHIBITED_CONTENT")
                ),
                candidates=None,
            )
        ),
    )

    result = await gemini_service.refine_text("raw transcript")

    assert result.text == "raw transcript"
    assert result.language == "und"
    assert result.problem_reason == "prompt_blocked:prohibited_content"
    call_config = gemini_service._CLIENT.models.calls[0]["config"]
    assert call_config["response_schema"] is gemini_service._RefinementPayload


@pytest.mark.anyio
async def test_refine_text_returns_candidate_finish_reason_when_no_text(monkeypatch):
    gemini_service = _load_gemini_service(
        monkeypatch,
        _FakeClient(
            response=SimpleNamespace(
                text=None,
                prompt_feedback=None,
                candidates=[
                    SimpleNamespace(finish_reason=SimpleNamespace(name="SAFETY"))
                ],
            )
        ),
    )

    result = await gemini_service.refine_text("raw transcript")

    assert result.text == "raw transcript"
    assert result.language == "und"
    assert result.problem_reason == "candidate_stopped:safety"


@pytest.mark.anyio
async def test_refine_text_returns_generic_reason_when_empty_response_has_no_metadata(monkeypatch):
    gemini_service = _load_gemini_service(
        monkeypatch,
        _FakeClient(response=SimpleNamespace(text=None, prompt_feedback=None, candidates=[])),
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
async def test_refine_text_reads_parsed_model_problem_reason(monkeypatch):
    client = _FakeClient()
    gemini_service = _load_gemini_service(monkeypatch, client)
    client.models._response = SimpleNamespace(
        text='{"fallback":"available"}',
        parsed=gemini_service._RefinementPayload(
            refined_text="Raw transcript.",
            language="EN",
            problem_reason="unclear_transcript",
        ),
    )

    result = await gemini_service.refine_text("raw transcript")

    assert result.text == "Raw transcript."
    assert result.language == "en"
    assert result.problem_reason == "unclear_transcript"


@pytest.mark.anyio
async def test_refine_text_falls_back_to_response_text_json(monkeypatch):
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
