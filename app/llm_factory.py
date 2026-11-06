"""Configuration and dependency construction for LLM adapters."""

from __future__ import annotations

import os

from app.llm import FakeLLM, LLMProvider
from app.llm_providers import OllamaLLM, VertexAILLM


def build_provider() -> LLMProvider:
    backend = os.getenv("LLM_BACKEND", "fake").strip().lower()
    timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    tokens = int(os.getenv("MAX_OUTPUT_TOKENS", "512"))
    if not 0 < timeout <= 180:
        raise ValueError("LLM_TIMEOUT_SECONDS must be between 0 and 180")
    if not 0 < tokens <= 4096:
        raise ValueError("MAX_OUTPUT_TOKENS must be between 1 and 4096")
    if backend == "fake":
        return FakeLLM()
    if backend == "ollama":
        return OllamaLLM(
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            timeout_seconds=timeout, max_output_tokens=tokens,
        )
    if backend in {"vertex", "vertex_ai"}:
        return VertexAILLM(
            project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
            model=os.getenv("GENAI_MODEL", "gemini-2.5-flash-lite"),
            max_output_tokens=tokens,
        )
    raise ValueError(f"Unsupported LLM_BACKEND: {backend}")
