"""Provider boundary to implement for Level 1."""

from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    async def generate(self, *, system: str, user: str) -> str: ...


class NotImplementedLLM:
    @property
    def model_name(self) -> str:
        return "not-implemented"

    async def generate(self, *, system: str, user: str) -> str:
        del system, user
        raise NotImplementedError("Implement a configured LLM provider for Level 1")

