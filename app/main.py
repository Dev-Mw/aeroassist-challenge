"""Starter HTTP application. Preserve the documented external contract."""

from __future__ import annotations

import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Response

from app import __version__
from app.agent import AeroAssistAgent
from app.schemas import (
    CapabilitiesResponse,
    CapabilityLevels,
    ChatRequest,
    ChatResponse,
)


def create_app(agent: AeroAssistAgent | None = None) -> FastAPI:
    application = FastAPI(title="AeroAssist", version=__version__)
    application.state.agent = agent or AeroAssistAgent()
    application.state.request_count = 0
    application.state.error_count = 0

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @application.get("/ready")
    async def ready() -> dict[str, object]:
        return {"status": "not_ready", "checks": {"assistant": False}}

    @application.get("/v1/capabilities", response_model=CapabilitiesResponse)
    async def capabilities() -> CapabilitiesResponse:
        return CapabilitiesResponse(
            challenge_version=__version__,
            levels=CapabilityLevels(
                foundation=False,
                core=False,
                tools_mcp=False,
                rag=False,
                production=False,
            ),
            llm_backend=os.getenv("LLM_BACKEND", "not-implemented"),
            tool_transport="none",
        )

    @application.post("/v1/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        request_id = uuid.uuid4().hex
        application.state.request_count += 1
        try:
            return await application.state.agent.chat(payload, request_id=request_id)
        except NotImplementedError as exc:
            application.state.error_count += 1
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        finally:
            _ = round((time.perf_counter() - started) * 1_000)

    @application.get("/metrics")
    async def metrics() -> Response:
        body = (
            f"aeroassist_requests_total {application.state.request_count}\n"
            f"aeroassist_errors_total {application.state.error_count}\n"
        )
        return Response(content=body, media_type="text/plain; version=0.0.4")

    return application


app = create_app()

