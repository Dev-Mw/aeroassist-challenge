"""Offline RAG quality checks (RAGAS-inspired, not the RAGAS library).

Reproducible metrics: retrieval recall@3, citation precision and answer coverage.
No model-as-judge scoring is represented as objective faithfulness.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.rag import Retriever

# Hand-authored synthetic reference cases, separate from the public evaluator.
CASES = [
    {"question": "Si me reacomodan, ¿conservo mi equipaje y puedo pedir reembolso?",
     "expected_docs": {"BAGGAGE-001", "REFUND-001"},
     "answer_terms": {"equipaje", "reembolso"}},
    {"question": "¿Qué ocurre con mi equipaje si cambian mi vuelo?",
     "expected_docs": {"BAGGAGE-001"}, "answer_terms": {"equipaje"}},
    {"question": "¿Qué prioridad tengo como cliente GOLD?",
     "expected_docs": {"LOYALTY-001"}, "answer_terms": {"gold"}},
    {"question": "¿Cuál será el precio del dólar mañana?",
     "expected_docs": set(), "answer_terms": set()},
    {"question": (
        "Si me reacomodan por cancelación, ¿conservo el equipaje y puedo pedir "
        "reembolso? También quiero saber qué prioridad tengo como GOLD."
    ),
     "expected_docs": {"BAGGAGE-001", "REFUND-001", "LOYALTY-001"},
     "answer_terms": {"equipaje", "reembolso", "prioridad"}},
]


def retrieve_metrics(retriever: Retriever) -> dict[str, float]:
    positive = [c for c in CASES if c["expected_docs"]]
    negatives = [c for c in CASES if not c["expected_docs"]]
    recall = []
    precision = []
    for case in positive:
        results = retriever.search_for_needs(case["question"], top_k=5)
        ids = {r.doc_id for r in results}
        recall.append(len(ids & case["expected_docs"]) / len(case["expected_docs"]))
        precision.append(len(ids & case["expected_docs"]) / len(ids) if ids else 0)
    abstained = sum(not retriever.search_for_needs(c["question"]) for c in negatives)
    return {
        "context_recall_at_5": sum(recall) / len(recall),
        "context_precision_at_5": sum(precision) / len(precision),
        "negative_abstention": abstained / len(negatives),
    }


def _chat_url(base_url: str) -> str:
    """Allow only HTTP(S) evaluator endpoints, never file:// or custom schemes."""
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Live evaluation requires an HTTP(S) base URL")
    return base_url.rstrip("/") + "/v1/chat"


def remote_metrics(base_url: str) -> dict[str, float]:
    citation_scores = []
    coverage_scores = []
    abstentions = []
    for case in CASES:
        body = json.dumps({"message": case["question"], "confirm_action": False}).encode()
        request = Request(  # noqa: S310 -- HTTP(S) validated by _chat_url
            _chat_url(base_url), data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urlopen(request, timeout=90) as response:  # noqa: S310
            result = json.load(response)
        ids = {c["doc_id"] for c in result.get("citations", [])}
        answer = result.get("answer", "").casefold()
        if case["expected_docs"]:
            citation_scores.append(len(ids & case["expected_docs"]) / len(ids) if ids else 0)
            coverage_scores.append(
                sum(t in answer for t in case["answer_terms"]) / len(case["answer_terms"])
            )
        else:
            abstentions.append(not ids and "no tengo evidencia" in answer)
    return {
        "citation_precision": sum(citation_scores) / len(citation_scores),
        "answer_topic_coverage": sum(coverage_scores) / len(coverage_scores),
        "unsupported_abstention": sum(abstentions) / len(abstentions),
    }


def case_details(retriever: Retriever, base_url: str | None = None) -> list[dict]:
    """Expose per-case failures instead of hiding them behind aggregate averages."""
    details = []
    for index, case in enumerate(CASES, start=1):
        expected = case["expected_docs"]
        retrieved = {c.doc_id for c in retriever.search_for_needs(case["question"], top_k=5)}
        missing = expected - retrieved
        record = {
            "case_id": f"rag-{index:02d}",
            "question_type": (
                "compound" if len(expected) > 1
                else "single" if expected else "unsupported"
            ),
            "expected_docs": sorted(expected),
            "retrieved_docs": sorted(retrieved),
            "missing_docs": sorted(missing),
            "context_recall": (
                len(expected & retrieved) / len(expected) if expected
                else float(not retrieved)
            ),
        }
        if base_url:
            body = json.dumps({"message": case["question"], "confirm_action": False}).encode()
            req = Request(  # noqa: S310 -- HTTP(S) validated by _chat_url
                _chat_url(base_url), data=body,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urlopen(req, timeout=90) as response:  # noqa: S310
                result = json.load(response)
            cited = {c["doc_id"] for c in result.get("citations", [])}
            answer = result.get("answer", "").casefold()
            terms = case["answer_terms"]
            record.update({
                "cited_docs": sorted(cited),
                "missing_citations": sorted(expected - cited),
                "answer_topic_coverage": (
                    sum(t in answer for t in terms) / len(terms)
                    if terms else float("no tengo evidencia" in answer and not cited)
                ),
            })
        record["status"] = "PASS" if (
            record["context_recall"] == 1.0
            and ("answer_topic_coverage" not in record or
                 (record["answer_topic_coverage"] == 1.0 and not record["missing_citations"]))
        ) else "FAIL"
        details.append(record)
    return details


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", help="Optionally test live HTTP replies (Ollama may be slow)")
    args = parser.parse_args()
    retriever = Retriever(Path(__file__).resolve().parents[1] / "knowledge_base")
    scores = retrieve_metrics(retriever)
    try:
        if args.base_url:
            scores.update(remote_metrics(args.base_url))
        cases = case_details(retriever, args.base_url)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print(f"Live evaluation failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(json.dumps({"index_version": retriever.index_version[:12],
                      "metrics": scores, "cases": cases}, indent=2, ensure_ascii=False))
    return 0 if all(score >= 0.65 for score in scores.values()) and all(
        case["status"] == "PASS" for case in cases
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
