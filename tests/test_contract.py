"""Guardrails, complete answers and extractive fallback: no external LLM required."""

from pathlib import Path

import pytest

from app.agent import AeroAssistAgent
from app.grounding import validate_generated_answer
from app.rag import Retriever
from app.schemas import ChatRequest
from scripts.evaluate_rag import retrieve_metrics

KB = Path(__file__).resolve().parents[1] / "knowledge_base"
QUESTION = "Si me reacomodan por cancelación, ¿mantengo equipaje y puedo pedir reembolso?"


class NoOperations:
    async def handle(self, request):
        return None


class Provider:
    model_name = "stub-llm"

    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    async def generate(self, *, system, user):
        self.calls += 1
        assert "BAGGAGE-001" in user and "REFUND-001" in user
        return self.reply


@pytest.mark.asyncio
async def test_multi_topic_generation_is_single_natural_answer():
    reply = """El equipaje incluido se mantiene. El reembolso es una alternativa si
        decide no viajar. La reacomodación no cobra penalidad."""
    provider = Provider(reply)
    agent = AeroAssistAgent(provider=provider, operations=NoOperations(),
                           retriever=Retriever(KB), generate_grounded=True)
    result = await agent.chat(ChatRequest(message=QUESTION), request_id="test")
    assert result.answer == reply
    assert provider.calls == 1
    assert {"BAGGAGE-001", "REFUND-001"}.issubset({c.doc_id for c in result.citations})


@pytest.mark.asyncio
async def test_incomplete_model_generation_falls_back_without_duplicate_text():
    provider = Provider("El equipaje incluido se mantiene.")
    agent = AeroAssistAgent(provider=provider, operations=NoOperations(),
                           retriever=Retriever(KB), generate_grounded=True)
    result = await agent.chat(ChatRequest(message=QUESTION), request_id="test")
    assert "reembolso" in result.answer.casefold()
    assert "Según la política" in result.answer
    assert "Explicación:" not in result.answer


def test_unsupported_number_is_rejected():
    evidence = Retriever(KB).search_diverse(QUESTION)
    valid, reason = validate_generated_answer(
        "El equipaje sigue incluido y el reembolso es de 9000 dólares.", evidence
    )
    assert not valid and reason == "unsupported_number"


def test_retrieval_eval_is_reproducible():
    first = retrieve_metrics(Retriever(KB))
    assert first == retrieve_metrics(Retriever(KB))
    assert first["context_recall_at_5"] == 1.0
