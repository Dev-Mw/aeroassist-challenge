"""Starter HTTP application. Preserve the documented external contract."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import time
import uuid
from threading import Lock

from fastapi import FastAPI, HTTPException, Request, Response

from app import __version__
from app.agent import AeroAssistAgent
from app.llm import FakeLLM
from app.observability import Metrics, configure_logging, logger
from app.operations import UnsafeOperation
from app.schemas import (
    CapabilitiesResponse,
    CapabilityLevels,
    ChatRequest,
    ChatResponse,
)


class ChatCapacity:
    """Process-local, nonblocking admission control for expensive chat requests.

    This bounds concurrent requests per worker; distributed limits belong at
    the ingress layer. No prompts or session identifiers are retained.
    """

    def __init__(self, limit: int) -> None:
        if not 1 <= limit <= 100:
            raise ValueError("MAX_CONCURRENT_CHATS must be between 1 and 100")
        self.limit = limit
        self.active = 0
        self.lock = Lock()

    def acquire(self) -> bool:
        with self.lock:
            if self.active >= self.limit:
                return False
            self.active += 1
            return True

    def release(self) -> None:
        with self.lock:
            self.active -= 1


def create_app(agent: AeroAssistAgent | None = None) -> FastAPI:
    application = FastAPI(title="AeroAssist", version=__version__)
    configure_logging()
    application.state.agent = agent or AeroAssistAgent()
    application.state.metrics = Metrics()
    application.state.chat_capacity = ChatCapacity(
        int(os.getenv("MAX_CONCURRENT_CHATS", "8"))
    )

    @application.middleware("http")
    async def record_request(request: Request, call_next):
        started = time.perf_counter()
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000)
            endpoint = request.url.path
            application.state.metrics.observe(
                endpoint=endpoint, status=status, seconds=duration_ms / 1000
            )
            safe_path = endpoint if endpoint in {
                "/health", "/ready", "/v1/chat", "/metrics", "/v1/capabilities"
            } else "other"
            logger.info("http_request", extra={
                "request_id": request_id, "path": safe_path,
                "method": request.method, "status_code": status,
                "duration_ms": duration_ms,
            })

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @application.get("/ready")
    async def ready() -> Response:
        # Check local model availability when supported; never call the model
        # to generate a response from a readiness probe.
        provider = application.state.agent.provider
        check = getattr(provider, "ready", None)
        available = True
        if check is not None:
            try:
                value = check()
                if inspect.isawaitable(value):
                    value = await asyncio.wait_for(value, timeout=2.0)
                available = bool(value)
            except Exception as exc:
                available = False
                logger.warning(
                    "readiness_check_failed", extra={"error_type": type(exc).__name__}
                )
        return Response(
            content=json.dumps({
                "status": "ready" if available else "not_ready",
                "checks": {"assistant": available},
            }),
            media_type="application/json",
            status_code=200 if available else 503,
        )

    @application.get("/v1/capabilities", response_model=CapabilitiesResponse)
    async def capabilities() -> CapabilitiesResponse:
        agent = application.state.agent
        fake_backend = isinstance(agent.provider, FakeLLM)
        return CapabilitiesResponse(
            challenge_version=__version__,
            levels=CapabilityLevels(
                # Cloud Run deployment and CD have not been validated.
                foundation=False,
                # The fake provider is only used for offline infrastructure tests.
                core=not fake_backend and agent.generate_grounded,
                tools_mcp=True,
                rag=True,
                # Production deployment is not yet verified on GCP.
                production=False,
            ),
            llm_backend=(
                "fake" if fake_backend else os.getenv("LLM_BACKEND", "custom")
            ),
            tool_transport="mcp",
        )

    @application.post("/v1/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        request_id = request.state.request_id
        capacity = application.state.chat_capacity
        if not capacity.acquire():
            raise HTTPException(
                status_code=429,
                detail={"error": {
                    "code": "concurrency_limit",
                    "message": "Too many concurrent requests",
                }, "request_id": request_id},
            )
        try:
            result = await application.state.agent.chat(payload, request_id=request_id)
            for trace in result.tool_calls:
                application.state.metrics.observe_tool(trace.name, trace.status)
            return result
        except UnsafeOperation as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "invalid_operation", "message": str(exc)},
                        "request_id": request_id},
            ) from exc
        except TimeoutError as exc:
            raise HTTPException(
                status_code=504,
                detail={"error": {"code": "provider_timeout", "message": "Provider timed out"},
                        "request_id": request_id},
            ) from exc
        except Exception as exc:
            logger.warning("chat_provider_failure", extra={
                "request_id": request_id, "error_type": type(exc).__name__,
            })
            raise HTTPException(
                status_code=502,
                detail={"error": {"code": "provider_error", "message": "Provider unavailable"},
                        "request_id": request_id},
            ) from exc
        finally:
            capacity.release()

    @application.get("/metrics")
    async def metrics() -> Response:
        return Response(
            content=application.state.metrics.render(),
            media_type="text/plain; version=0.0.4",
        )

    return application


app = create_app()

