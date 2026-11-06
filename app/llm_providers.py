"""Production LLM adapters behind the existing ``LLMProvider`` protocol.

Both providers generate text only; MCP execution and citations remain server-owned.
"""

from __future__ import annotations

import httpx2 as httpx

from app.llm import LLMProvider


class ProviderFailure(RuntimeError):
    """A configured upstream provider did not produce a usable response."""


class OllamaLLM(LLMProvider):
    def __init__(
        self, *, model: str, base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 60.0, max_output_tokens: int = 512,
    ) -> None:
        self._model = model
        # Do not accept arbitrary remote Ollama URLs: this adapter is intended
        # for a trusted local inference service, not an SSRF-capable proxy.
        parsed = httpx.URL(base_url)
        if parsed.scheme != "http" or parsed.host not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Ollama must use a localhost HTTP endpoint")
        self._base_url = str(parsed).rstrip("/")
        self._timeout = timeout_seconds
        self._tokens = max_output_tokens

    @property
    def model_name(self) -> str:
        return self._model

    async def ready(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
                models = response.json().get("models", [])
                return any(item.get("name", "").split(":")[0] == self._model.split(":")[0]
                           if ":" not in self._model else item.get("name") == self._model
                           for item in models)
        except (httpx.HTTPError, ValueError, KeyError):
            return False

    async def generate(self, *, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"num_predict": self._tokens, "temperature": 0},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout, trust_env=False) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
                response.raise_for_status()
            content = response.json().get("message", {}).get("content", "")
            if not isinstance(content, str) or not content.strip():
                raise ProviderFailure("Ollama returned an empty response")
            return content.strip()
        except httpx.TimeoutException as exc:
            raise TimeoutError("Ollama timed out") from exc
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise ProviderFailure("Ollama request failed") from exc


class VertexAILLM(LLMProvider):
    """Gemini via Google Gen AI SDK and Application Default Credentials."""

    def __init__(
        self, *, project: str, location: str, model: str,
        max_output_tokens: int = 512,
    ) -> None:
        if not project or project == "replace-me":
            raise ValueError("GOOGLE_CLOUD_PROJECT must be configured for Vertex AI")
        self._model = model
        self._tokens = max_output_tokens
        from google import genai

        self._client = genai.Client(vertexai=True, project=project, location=location)

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(self, *, system: str, user: str) -> str:
        from google.genai import types

        try:
            result = await self._client.aio.models.generate_content(
                model=self._model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=self._tokens,
                    temperature=0,
                ),
            )
            if not result.text or not result.text.strip():
                raise ProviderFailure("Vertex AI returned an empty response")
            return result.text.strip()
        except ProviderFailure:
            raise
        except Exception as exc:
            # Never expose SDK error messages (which may contain project metadata)
            # through the public HTTP response.
            raise ProviderFailure("Vertex AI generation failed") from exc
