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
    reply = (
        "El equipaje incluido se mantiene. El reembolso es una alternativa "
        "si decide no viajar. La reacomodación no cobra penalidad."
    )
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


def test_direct_baggage_evidence_is_ranked_above_unrelated_baggage_chunks():
    retriever = Retriever(KB)
    for question in (
        "¿Conservo mi equipaje si me reacomodan?",
        "Si cancelan mi vuelo, ¿mantengo el equipaje, puedo pedir reembolso "
        "y qué prioridad tengo como GOLD?",
    ):
        found = retriever.search_for_needs(question)
        baggage = next(chunk for chunk in found if chunk.doc_id == "BAGGAGE-001")
        assert "El equipaje incluido en la reserva original se mantiene" in baggage.text


def test_false_denial_of_explicit_baggage_policy_is_rejected():
    evidence = Retriever(KB).search_for_needs("¿Conservo mi equipaje si me reacomodan?")
    assert validate_generated_answer(
        "No se menciona explícitamente si se conserva el equipaje al reacomodar.",
        evidence,
    ) == (False, "contradicts_explicit_baggage_policy")


@pytest.mark.asyncio
async def test_agent_falls_back_on_baggage_policy_contradiction():
    class ContradictoryProvider:
        model_name = "test-provider"

        async def generate(self, *, system: str, user: str) -> str:
            return "No se menciona explícitamente si se conserva el equipaje al reacomodar."

    agent = AeroAssistAgent(
        provider=ContradictoryProvider(), operations=NoOperations(),
        retriever=Retriever(KB), generate_grounded=True,
    )
    result = await agent.chat(
        ChatRequest(message="¿Conservo mi equipaje si me reacomodan?"),
        request_id="contradiction",
    )
    assert "El equipaje incluido en la reserva original se mantiene" in result.answer
    assert "No se menciona" not in result.answer
    assert "BAGGAGE-001" in {citation.doc_id for citation in result.citations}


def test_refund_scope_shift_is_rejected_without_rejecting_valid_answer():
    evidence = Retriever(KB).search_for_needs(QUESTION, top_k=5)
    bad = (
        "Si cancelan tu vuelo, el equipaje incluido se mantiene al reacomodar. "
        "Sin embargo, no hay evidencia de que se te ofrezca un reembolso por el equipaje."
    )
    assert validate_generated_answer(bad, evidence, question=QUESTION) == (
        False, "refund_scope_mismatch"
    )
    good = (
        "Si cancelan el vuelo, conservas el equipaje incluido al reacomodarte. "
        "Como alternativa, puedes elegir no viajar y solicitar devolución "
        "al medio de pago original."
    )
    assert validate_generated_answer(good, evidence, question=QUESTION)[0]


@pytest.mark.asyncio
async def test_agent_does_not_present_baggage_refund_as_answer_to_trip_refund():
    reply = (
        "Si cancelan tu vuelo, el equipaje incluido se mantiene al reacomodar. "
        "Sin embargo, no hay evidencia de que se te ofrezca un reembolso por el equipaje."
    )
    agent = AeroAssistAgent(
        provider=Provider(reply), operations=NoOperations(),
        retriever=Retriever(KB), generate_grounded=True,
    )
    result = await agent.chat(ChatRequest(message=QUESTION), request_id="refund-regression")
    assert "reembolso por el equipaje" not in result.answer.casefold()
    assert "no viajar" in result.answer.casefold()
    assert {"BAGGAGE-001", "REFUND-001"}.issubset(
        {citation.doc_id for citation in result.citations}
    )
