"""Regression checks for policy retrieval and evidence-based responses."""

from pathlib import Path

import pytest

from app.agent import AeroAssistAgent
from app.rag import Retriever
from app.schemas import ChatRequest

KB = Path(__file__).resolve().parents[1] / "knowledge_base"


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Si me reacomodan por una cancelación, ¿mantengo el equipaje incluido?", "BAGGAGE-001"),
        ("¿Me dan hotel por una espera larga?", "CARE-001"),
        ("¿Puedo pedir reembolso si cancelan mi vuelo?", "REFUND-001"),
        ("¿Qué pasa con mi silla de ruedas si me reacomodan?", "SSR-001"),
        ("¿Qué prioridad tiene un cliente GOLD?", "LOYALTY-001"),
        ("¿Se cobra penalidad al reacomodar una cancelación?", "IRROPS-001"),
    ],
)
def test_retriever_precision_at_one(question: str, expected: str) -> None:
    documents = Retriever(KB).search(question)
    assert documents and documents[0].doc_id == expected
    assert documents[0].score > 0


@pytest.mark.parametrize(
    "question",
    ["¿Cuál será el precio del dólar mañana?", "¿Se permite llevar mascotas en un vuelo?"],
)
def test_retriever_abstains_without_policy_evidence(question: str) -> None:
    assert Retriever(KB).search(question) == []


def test_index_version_changes_only_when_corpus_changes(tmp_path: Path) -> None:
    (tmp_path / "baggage.md").write_bytes((KB / "baggage.md").read_bytes())
    retriever = Retriever(tmp_path)
    first = retriever.index_version
    assert retriever.refresh() == first
    path = tmp_path / "baggage.md"
    path.write_text(
        path.read_text(encoding="utf-8") + "\nNuevo texto sintético.\n",
        encoding="utf-8",
    )
    assert retriever.refresh() != first


@pytest.mark.asyncio
async def test_agent_cites_the_policy_without_invoking_llm() -> None:
    class Provider:
        @property
        def model_name(self):
            return "no-llm-policy"

        async def generate(self, *, system, user):
            raise AssertionError("Policy answer must not rely on fake or ungrounded provider")

    class NoOperations:
        async def handle(self, request):
            return None

    agent = AeroAssistAgent(provider=Provider(), operations=NoOperations(), retriever=Retriever(KB))
    response = await agent.chat(
        ChatRequest(message="¿Mantengo el equipaje incluido cuando me reacomodan?"),
        request_id="rag-test",
    )
    assert response.citations[0].doc_id == "BAGGAGE-001"
    assert "equipaje incluido" in response.answer
    assert response.tool_calls == []


def test_http_policy_response_contains_real_citation() -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    class NoOperations:
        async def handle(self, request):
            return None

    agent = AeroAssistAgent(operations=NoOperations())
    client = TestClient(create_app(agent))
    reply = client.post("/v1/chat", json={
        "message": "Si me reacomodan por cancelación, ¿mantengo el equipaje incluido?",
        "session_id": "rag-http-test", "confirm_action": False,
    })
    assert reply.status_code == 200
    body = reply.json()
    assert body["citations"][0]["doc_id"] == "BAGGAGE-001"
    assert "equipaje incluido" in body["answer"]
    assert body["tool_calls"] == []


def test_multi_topic_retrieval_covers_baggage_and_refund() -> None:
    results = Retriever(KB).search_diverse(
        "Si me reacomodan por cancelación, ¿conservo mi equipaje y puedo pedir reembolso?"
    )
    ids = [item.doc_id for item in results]
    assert "BAGGAGE-001" in ids
    assert "REFUND-001" in ids
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_multi_topic_agent_passes_all_evidence_to_llm() -> None:
    class RecordingProvider:
        model_name = "recording-provider"
        context = ""

        async def generate(self, *, system: str, user: str) -> str:
            self.context = user
            return "El equipaje incluido se conserva; el reembolso es una alternativa si no viaja."

    class NoOperations:
        async def handle(self, request):
            return None

    provider = RecordingProvider()
    agent = AeroAssistAgent(
        provider=provider, operations=NoOperations(), retriever=Retriever(KB),
        generate_grounded=True,
    )
    response = await agent.chat(
        ChatRequest(message="Si me reacomodan, ¿mantengo equipaje y hay reembolso?"),
        request_id="multi-doc",
    )
    assert {"BAGGAGE-001", "REFUND-001"}.issubset(
        {citation.doc_id for citation in response.citations}
    )
    assert "BAGGAGE-001" in provider.context and "REFUND-001" in provider.context
    assert "equipaje" in response.answer and "reembolso" in response.answer
