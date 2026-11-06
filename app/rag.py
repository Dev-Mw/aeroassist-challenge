"""Local, versioned lexical retrieval over the synthetic policy corpus.

The index contains only policy text, not operational facts. It is built on
initialization, and can be explicitly refreshed after a corpus deployment.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class RetrievedChunk:
    doc_id: str
    title: str
    chunk_id: str
    text: str
    score: float


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    # Small, documented query expansion: alternative Spanish terms for the
    # same policy concepts. Does not introduce facts or change the documents.
    substitutions = {
        "reacomodan": "reacomodacion", "reacomodarme": "reacomodacion",
        "conservo": "mantiene", "conservar": "mantiene",
        "mantengo": "mantiene", "mantener": "mantiene",
        "conserva": "mantiene",
        "reacomodar": "reacomodacion", "reubicacion": "reacomodacion",
        "maleta": "equipaje", "maletas": "equipaje",
        "valija": "equipaje", "valijas": "equipaje",
        "cancelan": "cancelacion", "cancelado": "cancelacion",
        "cancelada": "cancelacion", "compensacion": "asistencia",
        "hospedaje": "alojamiento", "hotel": "alojamiento",
        "devolucion": "reembolso", "devolver": "reembolso",
        "ruedas": "wchr", "silla": "asistencia",
        "especiales": "especial", "retrasan": "retraso",
    }
    return re.sub(r"\b[\w]+\b", lambda m: substitutions.get(m.group(), m.group()), text)


def _parse_policy(path: Path) -> tuple[str, str, str, str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n") or "\n---\n" not in raw[4:]:
        raise ValueError(f"Missing front matter in {path.name}")
    metadata, body = raw[4:].split("\n---\n", 1)
    attrs = dict(
        line.split(":", 1) for line in metadata.splitlines()
        if ":" in line
    )
    doc_id = attrs.get("doc_id", "").strip()
    title = attrs.get("title", "").strip()
    version = attrs.get("version", "").strip()
    if not (doc_id and title and version):
        raise ValueError(f"Missing policy identity/version in {path.name}")
    return doc_id, title, version, body


class Retriever:
    def __init__(self, knowledge_base: Path) -> None:
        self.knowledge_base = knowledge_base
        self.chunks: list[RetrievedChunk] = []
        self.index_version = ""
        self._word = TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode", sublinear_tf=True)
        self._char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self.refresh()

    def refresh(self) -> str:
        """Rebuild atomically; call after deploying a versioned corpus."""
        files = sorted(self.knowledge_base.glob("*.md"))
        if not files:
            raise ValueError("No policy documents found")
        chunks: list[RetrievedChunk] = []
        digester = hashlib.sha256()
        used_ids: set[str] = set()
        for file in files:
            raw = file.read_bytes()
            digester.update(file.name.encode("utf-8") + b"\0" + raw)
            doc_id, title, version, body = _parse_policy(file)
            if doc_id in used_ids:
                raise ValueError(f"Duplicate doc_id: {doc_id}")
            used_ids.add(doc_id)
            # Paragraph-level chunks preserve local evidence and stable IDs.
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
            for number, paragraph in enumerate(paragraphs, start=1):
                if paragraph.startswith("#") or paragraph.startswith(">"):
                    continue
                chunks.append(RetrievedChunk(doc_id, title, f"{doc_id}#p{number}", paragraph, 0.0))
        if not chunks:
            raise ValueError("No indexable policy paragraphs")
        corpus = [_normalize(f"{c.title} {c.text}") for c in chunks]
        word_matrix = self._word.fit_transform(corpus)
        char_matrix = self._char.fit_transform(corpus)
        self.chunks = chunks
        self._word_matrix = word_matrix
        self._char_matrix = char_matrix
        self.index_version = digester.hexdigest()
        return self.index_version

    def search(self, query: str, *, top_k: int = 3) -> list[RetrievedChunk]:
        if not query.strip() or top_k <= 0:
            return []
        normalized = _normalize(query)
        words = self._word.transform([normalized])
        chars = self._char.transform([normalized])
        # An unrelated query with no shared words should not be treated as
        # evidence merely because it shares character sequences.
        word_scores = cosine_similarity(words, self._word_matrix)[0]
        char_scores = cosine_similarity(chars, self._char_matrix)[0]
        ranked = sorted(
            ((0.8 * float(w) + 0.2 * float(c), index, float(w))
             for index, (w, c) in enumerate(zip(word_scores, char_scores, strict=True))),
            reverse=True,
        )
        # Domain-specific vocabulary is used ONLY to rerank evidence, never
        # to generate an answer. This prevents generic words such as "vuelo"
        # from triggering irrelevant citations for unsupported subjects.
        anchors = {
            "BAGGAGE-001": {"equipaje", "maleta", "maletas", "valija", "valijas"},
            "CARE-001": {"alojamiento", "hotel", "comida", "refrigerio", "bebida", "espera"},
            "SSR-001": {"wchr", "wchs", "wchc", "silla", "ruedas", "movilidad", "especial"},
            "LOYALTY-001": {"gold", "platinum", "fidelidad", "prioridad"},
            "REFUND-001": {"reembolso", "devolucion", "devolver"},
            "SAFETY-001": {"inyeccion", "credenciales", "prompt", "instrucciones"},
            "IRROPS-001": {"penalidad", "tarifa", "reacomodacion", "disrupcion"},
        }
        query_terms = set(re.findall(r"\w+", normalized))
        supported_docs = {
            doc_id for doc_id, tokens in anchors.items() if query_terms & tokens
        }
        if not supported_docs:
            return []
        ranked = sorted(
            ((score + (0.2 if self.chunks[index].doc_id in supported_docs else 0.0), index, word)
             for score, index, word in ranked),
            reverse=True,
        )
        results: list[RetrievedChunk] = []
        for score, index, word_score in ranked:
            chunk = self.chunks[index]
            if chunk.doc_id not in supported_docs or score < 0.265 or word_score < 0.04:
                continue
            results.append(RetrievedChunk(chunk.doc_id, chunk.title, chunk.chunk_id,
                                          chunk.text, min(1.0, max(0.0, score))))
            if len(results) >= top_k:
                break
        return results

    def search_diverse(self, query: str, *, top_k: int = 4) -> list[RetrievedChunk]:
        """Select the best grounded paragraph per document for multi-topic questions.

        Keep the scored lexical retriever unchanged; diversify only after ranking,
        avoiding duplicate chunks from one policy crowding out another policy.
        """
        candidates = self.search(query, top_k=max(top_k * 4, len(self.chunks)))
        selected: list[RetrievedChunk] = []
        seen: set[str] = set()
        for chunk in candidates:
            if chunk.doc_id not in seen:
                selected.append(chunk)
                seen.add(chunk.doc_id)
            if len(selected) == top_k:
                break
        return selected

    def search_for_needs(
        self, query: str, *, top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Cover distinct policy needs without introducing a second index.

        Split at explicit question/conjunction boundaries, then use the existing
        scored retrieval independently for each segment. The original complete
        query is also searched to preserve contextual recall.
        """
        if top_k <= 0:
            return []
        parts = [p.strip(" ,?¿;:.") for p in re.split(
            r"[?;]+|\b(?:pero tambien|y tambien|ademas|asimismo)\b",
            _normalize(query), flags=re.IGNORECASE,
        ) if p.strip(" ,?¿;:.")]
        # No more than six needs; input is already limited by the API contract.
        queries = [query, *parts[:6]]
        found: dict[str, RetrievedChunk] = {}
        for part in queries:
            for chunk in self.search_diverse(part, top_k=top_k):
                existing = found.get(chunk.doc_id)
                if existing is None or chunk.score > existing.score:
                    found[chunk.doc_id] = chunk
        # Preserve relevance order with a guaranteed unique doc_id.
        return sorted(found.values(), key=lambda c: c.score, reverse=True)[:top_k]
