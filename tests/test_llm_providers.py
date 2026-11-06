"""Offline adapter/grounding tests; no cloud account or Ollama daemon needed."""

from __future__ import annotations

from pathlib import Path

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.agent import AeroAssistAgent
from app.llm import FakeLLM, LLMProvider
from app.llm_factory import build_provider
from app.llm_providers import OllamaLLM, ProviderFailure
from app.main import create_app
from app.rag import Retriever
from app.schemas import ChatRequest


class StubOperations:
    async def handle(self, request):
        return None


@pytest.mark.asyncio
async def test_ollama_sends_bounded_non_streaming_chat(monkeypatch):
    captured = {}

    async def mock_post(self, url, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs["json"]
        return httpx.Response(
            200, json={"message": {"content": "  respuesta  "}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    provider = OllamaLLM(model="llama3.2", max_output_tokens=70)
    result = await provider.generate(system="Reglas", user="Pregunta")
    assert result == "respuesta"
    assert captured["url"].endswith("/api/chat")
    assert captured["payload"]["options"]["num_predict"] == 70
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["messages"][0]["role"] == "system"


@pytest.mark.asyncio
async def test_ollama_timeout_is_bounded(monkeypatch):
    async def timeout(self, url, **kwargs):
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(httpx.AsyncClient, "post", timeout)
    with pytest.raises(TimeoutError):
        await OllamaLLM(model="local").generate(system="a", user="b")


@pytest.mark.asyncio
async def test_ollama_empty_response_raises(monkeypatch):
    async def empty(self, url, **kwargs):
        return httpx.Response(
            200, json={"message": {"content": " "}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", empty)
    with pytest.raises(ProviderFailure):
        await OllamaLLM(model="local").generate(system="a", user="b")


def test_ollama_must_be_localhost():
    with pytest.raises(ValueError):
        OllamaLLM(model="local", base_url="http://example.com:11434")


def test_provider_factory_selection(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")
    assert build_provider().model_name == "test-model"
    monkeypatch.setenv("LLM_BACKEND", "unknown")
    with pytest.raises(ValueError):
        build_provider()


def test_vertex_requires_project(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "vertex_ai")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
        build_provider()


@pytest.mark.asyncio
async def test_policy_uses_real_provider_without_loosening_citation():
    class GeneratingProvider:
        model_name = "local-demo"
        calls = 0

        async def generate(self, *, system, user):
            self.calls += 1
            assert "equipaje" in user
            assert "Evidencia documental" in user
            return "El equipaje incluido se mantiene al reacomodar."

    provider = GeneratingProvider()
    agent = AeroAssistAgent(
        provider=provider, operations=StubOperations(),
        retriever=Retriever(Path(__file__).resolve().parents[1] / "knowledge_base"),
        generate_grounded=True,
    )
    result = await agent.chat(
        ChatRequest(message="¿Mantengo mi equipaje incluido si me reacomodan?"),
        request_id="a",
    )
    assert provider.calls == 1
    assert result.citations[0].doc_id == "BAGGAGE-001"
    assert result.answer == "El equipaje incluido se mantiene al reacomodar."
    assert result.tool_calls == []


@pytest.mark.asyncio
async def test_no_evidence_must_not_call_generating_model():
    class ForbiddenProvider:
        model_name = "local"

        async def generate(self, *, system, user):
            raise AssertionError("unsupported question must abstain")

    agent = AeroAssistAgent(
        provider=ForbiddenProvider(), operations=StubOperations(), generate_grounded=True,
    )
    response = await agent.chat(
        ChatRequest(message="¿Cuál será el precio del dólar mañana?"), request_id="b",
    )
    assert response.citations == []
    assert "No tengo evidencia" in response.answer


def test_readiness_reports_unavailable_local_model():
    class UnreadyProvider:
        model_name = "not-installed"

        async def ready(self):
            return False

    agent = AeroAssistAgent(provider=UnreadyProvider(), operations=StubOperations())
    response = TestClient(create_app(agent)).get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


@pytest.mark.asyncio
async def test_unsupported_model_summary_is_not_added():
    class HallucinatingProvider:
        model_name = "test-model"

        async def generate(self, *, system, user):
            return "Los pasajeros reciben un reembolso de 9000 dólares en efectivo."

    agent = AeroAssistAgent(
        provider=HallucinatingProvider(), operations=StubOperations(),
        generate_grounded=True,
    )
    result = await agent.chat(
        ChatRequest(message="¿Mantengo mi equipaje incluido si me reacomodan?"),
        request_id="hallucination",
    )
    assert "9000" not in result.answer
    assert result.citations[0].doc_id == "BAGGAGE-001"

@pytest.mark.asyncio
async def test_ollama_readiness_checks_configured_model(monkeypatch):
    async def mock_get(self, url):
        return httpx.Response(
            200, json={"models": [{"name": "llama3.2:latest"}]},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    assert await OllamaLLM(model="llama3.2").ready() is True
    assert await OllamaLLM(model="missing").ready() is False


@pytest.mark.asyncio
async def test_vertex_ai_adapter_uses_sdk_without_real_credentials():
    from types import SimpleNamespace

    pytest.importorskip("google.genai")
    from app.llm_providers import VertexAILLM

    captured = {}

    class Models:
        async def generate_content(self, *, model, contents, config):
            captured.update(model=model, contents=contents, config=config)
            return SimpleNamespace(text=" Una respuesta ")

    provider = VertexAILLM.__new__(VertexAILLM)
    provider._model = "gemini-test"
    provider._tokens = 64
    provider._client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    assert await provider.generate(system="Solo evidencia", user="Pregunta") == "Una respuesta"
    assert captured["model"] == "gemini-test"
    assert captured["config"].max_output_tokens == 64
    assert captured["config"].system_instruction == "Solo evidencia"


def test_llm_adapters_explicitly_implement_provider_contract():
    """Keep adapters visibly linked to the factory's return type."""
    from app.llm_providers import VertexAILLM

    for adapter in (FakeLLM, OllamaLLM, VertexAILLM):
        assert LLMProvider in adapter.__mro__


def test_factory_returns_a_provider_implementation(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "ollama")
    provider: LLMProvider = build_provider()
    assert isinstance(provider, OllamaLLM)
