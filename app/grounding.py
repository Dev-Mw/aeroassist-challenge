"""Conservative offline checks before exposing LLM-written policy answers.

These rules are guardrails, NOT a semantic entailment or RAGAS faithfulness score.
The retrieval layer remains the only authority for citation provenance.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from app.rag import RetrievedChunk

_STOPWORDS = frozenset({
    "a", "al", "ante", "con", "de", "del", "el", "en", "la", "las", "lo",
    "los", "para", "por", "sobre", "una", "un", "y", "o", "su", "si",
    "que", "como", "es", "puede", "se", "documento", "politica",
})


def _ascii_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _terms(text: str) -> set[str]:
    normalized = _ascii_lower(text)
    return {t for t in re.findall(r"[a-z]+", normalized) if len(t) > 3 and t not in _STOPWORDS}


def _stem(term: str) -> str:
    """Very small shared-prefix check, not a language-specific morphological analyzer."""
    return term[: min(6, len(term))]


def missing_topic_chunks(answer: str, evidence: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
    """Identify policy topics absent from a draft; not a semantic entailment check."""
    answer_terms = {_stem(t) for t in _terms(answer)}
    return [
        chunk for chunk in evidence
        if (title_terms := {_stem(t) for t in _terms(chunk.title)})
        and not (title_terms & answer_terms)
    ]


def title_coverage(answer: str, evidence: Sequence[RetrievedChunk]) -> bool:
    """Ensure the answer mentions at least one topic term from each cited title."""
    return not missing_topic_chunks(answer, evidence)


def validate_generated_answer(
    answer: str, evidence: Sequence[RetrievedChunk], *, max_length: int = 1200,
    question: str | None = None,
) -> tuple[bool, str]:
    """Reject obvious unsupported claims; unknown entailment remains an explicit limitation."""
    if not answer.strip() or len(answer) > max_length:
        return False, "empty_or_oversized"
    if re.search(r"https?://|www\.", answer, flags=re.IGNORECASE):
        return False, "untrusted_url"
    if "SIN_RESUMEN" in answer:
        return False, "provider_abstained"
    # A common hallucination is denying that the policy contains a rule
    # even when the retrieved paragraph states it explicitly. This narrow
    # guard protects the demonstrated baggage case; it is not an NLI model.
    normalized_answer = " ".join(_terms(answer))
    normalized_evidence = " ".join(_terms(" ".join(c.text for c in evidence)))
    denial = re.search(
        r"no\s+(?:se\s+)?(?:menciona|indica|especifica)|"
        r"no\s+(?:hay|tengo)\s+(?:informacion|datos)",
        _ascii_lower(answer),
    )
    if (denial and "equipaje" in normalized_answer
            and "equipaje" in normalized_evidence
            and "mantiene" in normalized_evidence
            and "incluido" in normalized_evidence):
        return False, "contradicts_explicit_baggage_policy"
    # Prevent a documented failure: a refund question about a cancelled trip
    # was reinterpreted as an unsupported refund *of baggage*. Source coverage
    # and citations alone cannot detect this change of subject.
    if question is not None:
        normalized_question = _ascii_lower(question)
        normalized_response = _ascii_lower(answer)
        has_refund_policy = any(chunk.doc_id == "REFUND-001" for chunk in evidence)
        asks_trip_refund = (
            any(term in normalized_question for term in ("reembolso", "devolucion"))
            and any(term in normalized_question for term in ("cancel", "vuelo"))
            and not re.search(
                r"(?:reembolso|devolucion)\s+(?:por|del|de)\s+(?:el\s+)?equipaje",
                normalized_question,
            )
        )
        refund_of_baggage = re.search(
            r"(?:reembolso|devolucion)\s+(?:por|del|de)\s+(?:el\s+)?equipaje",
            normalized_response,
        )
        if has_refund_policy and asks_trip_refund and refund_of_baggage:
            return False, "refund_scope_mismatch"
    context = " ".join(c.text for c in evidence)
    # Document IDs should not authorize new amounts, dates or deadlines.
    numbers = set(re.findall(r"\d+(?:[.,]\d+)?", answer))
    source_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", context))
    if not numbers.issubset(source_numbers):
        return False, "unsupported_number"
    if not title_coverage(answer, evidence):
        return False, "incomplete_topic_coverage"
    return True, "accepted"
