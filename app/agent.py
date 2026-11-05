"""Application orchestration boundary for the progressive levels."""

from __future__ import annotations

from app.schemas import ChatRequest, ChatResponse


class AeroAssistAgent:
    async def chat(self, request: ChatRequest, *, request_id: str) -> ChatResponse:
        del request, request_id
        raise NotImplementedError(
            "Productize the notebook, then add MCP tools and RAG progressively"
        )

