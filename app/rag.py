"""Retrieval boundary to implement for Level 3."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RetrievedChunk:
    doc_id: str
    title: str
    chunk_id: str
    text: str
    score: float


class Retriever:
    def __init__(self, knowledge_base: Path) -> None:
        self.knowledge_base = knowledge_base

    def search(self, query: str, *, top_k: int = 3) -> list[RetrievedChunk]:
        del query, top_k
        raise NotImplementedError("Implement retrieval and evaluation for Level 3")

