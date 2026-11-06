"""LLM provider boundary and deterministic offline implementation.

The fake backend is intended for local tests, not as a deployed generative model.
"""

from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    async def generate(self, *, system: str, user: str) -> str: ...


class FakeLLM(LLMProvider):
    """Deterministic adapter useful for contract tests without network access."""

    @property
    def model_name(self) -> str:
        return "fake-local-v1"

    async def generate(self, *, system: str, user: str) -> str:
        del system
        normalized = user.casefold()
        if any(
            term in normalized
            for term in ("qué puedes", "que puedes", "tipo de ayuda", "capacidades")
        ):
            return (
                "Puedo ayudar con el estado de un vuelo, el contexto de una reserva, "
                "alternativas de reacomodación y políticas sintéticas. "
                "Las operaciones requieren conexión con las herramientas MCP."
            )
        return (
            "No tengo evidencia suficiente para responder esa pregunta. "
            "Puedo ayudar con vuelos, reservas y políticas sintéticas del ejercicio."
        )
