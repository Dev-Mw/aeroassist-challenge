"""Regression cases discovered in multi-intent manual testing."""
from pathlib import Path

import pytest

from app.agent import AeroAssistAgent
from app.rag import Retriever
from app.schemas import ChatRequest
from scripts.evaluate_rag import case_details

KB = Path(__file__).resolve().parents[1] / "knowledge_base"


class NoOperations:
    async def handle(self, request):
        return None


class CapturingProvider:
    model_name = "test-provider"

    def __init__(self):
        self.prompt = None

    async def generate(self, *, system, user):
        self.prompt = user
        return (
            "El equipaje se mantiene, el reembolso es una alternativa "
            "y la prioridad depende de fidelidad."
        )


def test_compound_three_topic_retrieval():
    question = ("Si me reacomodan por cancelación, ¿conservo equipaje y tengo derecho "
                "a reembolso?, pero también quiero saber si tengo prioridad")
    found = Retriever(KB).search_for_needs(question)
    assert {"BAGGAGE-001", "REFUND-001", "LOYALTY-001"}.issubset(
        {item.doc_id for item in found}
    )


@pytest.mark.asyncio
async def test_compound_prompt_and_citations_include_all_needs():
    provider = CapturingProvider()
    agent = AeroAssistAgent(provider=provider, operations=NoOperations(),
                           retriever=Retriever(KB), generate_grounded=True)
    question = "¿Conservo equipaje y tengo reembolso? También quiero saber si tengo prioridad."
    result = await agent.chat(ChatRequest(message=question), request_id="t")
    for doc_id in ("BAGGAGE-001", "REFUND-001", "LOYALTY-001"):
        assert doc_id in provider.prompt
        assert doc_id in {cite.doc_id for cite in result.citations}


@pytest.mark.asyncio
async def test_context_limit_is_enforced(monkeypatch):
    monkeypatch.setenv("RAG_CONTEXT_MAX_CHARS", "1000")
    provider = CapturingProvider()
    agent = AeroAssistAgent(provider=provider, operations=NoOperations(),
                           retriever=Retriever(KB), generate_grounded=True)
    result = await agent.chat(ChatRequest(message="¿Conservo mi equipaje?"), request_id="t")
    assert result.answer
    if provider.prompt:
        assert len(provider.prompt) < 1000


def test_per_case_evaluation_shows_compound_cases():
    cases = case_details(Retriever(KB))
    assert any(c["question_type"] == "compound" and len(c["expected_docs"]) == 3
               and c["status"] == "PASS" for c in cases)

@pytest.mark.asyncio
async def test_three_topic_generation_completes_only_missing_policy():
    class PartialProvider:
        model_name = "partial-provider"

        async def generate(self, *, system, user):
            assert "REFUND-001" in user
            return (
                "El equipaje incluido se mantiene y la prioridad GOLD "
                "permite escalamiento humano."
            )

    agent = AeroAssistAgent(
        provider=PartialProvider(), operations=NoOperations(),
        retriever=Retriever(KB), generate_grounded=True,
    )
    result = await agent.chat(ChatRequest(message=(
        "Si me reacomodan por cancelación, ¿conservo el equipaje y puedo pedir "
        "reembolso? También quiero saber qué prioridad tengo como GOLD."
    )), request_id="three-topic")
    assert "reembolso" in result.answer.casefold()
    assert "equipaje" in result.answer.casefold()
    assert "prioridad" in result.answer.casefold()
    assert "Según la política «Alternativa de reembolso»" in result.answer
    assert result.answer.count("Según la política «Equipaje en una reacomodación»") == 0
    assert {"REFUND-001", "BAGGAGE-001", "LOYALTY-001"}.issubset(
        {citation.doc_id for citation in result.citations}
    )
