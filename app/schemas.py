"""Stable HTTP schemas used by public and private evaluators."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4_000)
    session_id: str | None = Field(default=None, max_length=128)
    confirm_action: bool = False

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class Citation(BaseModel):
    doc_id: str
    title: str
    chunk_id: str
    score: float = Field(ge=0.0, le=1.0)


class ToolCallTrace(BaseModel):
    name: str
    arguments: dict[str, Any]
    status: str
    duration_ms: int = Field(ge=0)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)
    requires_confirmation: bool = False
    request_id: str
    model: str
    latency_ms: int = Field(ge=0)


class CapabilityLevels(BaseModel):
    foundation: bool
    core: bool
    tools_mcp: bool
    rag: bool
    production: bool


class CapabilitiesResponse(BaseModel):
    challenge_version: str
    levels: CapabilityLevels
    llm_backend: str
    tool_transport: str

