"""Local quality check: retrieval P@1, hit@3, and negative abstention."""

from __future__ import annotations

from pathlib import Path

from app.rag import Retriever

CASES = [
    ("Si me reacomodan por cancelación, ¿mantengo el equipaje incluido?", "BAGGAGE-001"),
    ("¿Tengo derecho a comida y hotel por una espera larga?", "CARE-001"),
    ("¿Puedo solicitar un reembolso tras cancelación?", "REFUND-001"),
    ("¿Se conserva la asistencia de silla de ruedas al reacomodar?", "SSR-001"),
    ("¿Qué prioridad tiene un cliente GOLD?", "LOYALTY-001"),
    ("¿Hay penalidad por reacomodación?", "IRROPS-001"),
    ("¿Cuánto valdrá el dólar mañana?", None),
    ("¿Se permiten mascotas en cabina?", None),
]


def main() -> int:
    retriever = Retriever(Path(__file__).resolve().parents[1] / "knowledge_base")
    correct_at_1 = hits_at_3 = negative_correct = 0
    positives = sum(expected is not None for _, expected in CASES)
    negatives = len(CASES) - positives
    for query, expected in CASES:
        results = retriever.search(query, top_k=3)
        ids = [item.doc_id for item in results]
        if expected is None:
            negative_correct += not ids
        else:
            correct_at_1 += bool(ids and ids[0] == expected)
            hits_at_3 += expected in ids
        print(f"{'OK' if (not ids if expected is None else ids[:1] == [expected]) else 'FAIL'} "
              f"expected={expected} retrieved={ids}")
    print(f"index_version={retriever.index_version[:12]}")
    print(f"precision_at_1={correct_at_1}/{positives} "
          f"hit_at_3={hits_at_3}/{positives} "
          f"negative_abstention={negative_correct}/{negatives}")
    return 0 if correct_at_1 == hits_at_3 == positives and negative_correct == negatives else 1


if __name__ == "__main__":
    raise SystemExit(main())
