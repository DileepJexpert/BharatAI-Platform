"""Async HTTP client for Ollama's /api/chat endpoint."""

import json
import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT_SECONDS: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))


class OllamaConnectionError(Exception):
    """Raised when Ollama is unreachable."""
    pass


class OllamaTimeoutError(Exception):
    """Raised when Ollama request exceeds timeout."""
    pass


class OllamaModelNotLoadedError(Exception):
    """Raised when the requested model is not loaded in Ollama."""
    pass


class OllamaError(Exception):
    """Generic Ollama error."""
    pass


@dataclass
class LLMResponse:
    """Response from Ollama chat endpoint."""
    text: str
    model: str
    total_duration_ms: int
    prompt_eval_count: int
    eval_count: int


class OllamaClient:
    """Async client for Ollama's /api/chat endpoint."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self.timeout = timeout or OLLAMA_TIMEOUT_SECONDS
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-initialise httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        system: str,
        user: str,
        model: str,
    ) -> LLMResponse:
        """Send a chat request to Ollama.

        Args:
            system: system prompt text.
            user: user message text.
            model: Ollama model tag (e.g. 'llama3.2:3b-instruct-q4_0').

        Returns:
            LLMResponse with the model's reply.

        Raises:
            OllamaTimeoutError: on timeout (>30s default).
            OllamaConnectionError: if Ollama is unreachable.
            OllamaModelNotLoadedError: if model isn't loaded.
            OllamaError: for other HTTP errors.
        """
        client = await self._get_client()

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }

        logger.info("[LLM] Sending request to Ollama model=%s...", model)
        try:
            response = await client.post("/api/chat", json=payload)
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(
                f"Ollama request timed out after {self.timeout}s"
            ) from exc
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at {self.base_url}: {exc}"
            ) from exc

        if response.status_code == 404:
            raise OllamaModelNotLoadedError(
                f"Model '{model}' not found in Ollama. Pull it first: ollama pull {model}"
            )

        if response.status_code != 200:
            raise OllamaError(
                f"Ollama returned HTTP {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise OllamaError(f"Invalid JSON from Ollama: {response.text}") from exc

        message = data.get("message", {})

        result = LLMResponse(
            text=message.get("content", ""),
            model=data.get("model", model),
            total_duration_ms=data.get("total_duration", 0) // 1_000_000,
            prompt_eval_count=data.get("prompt_eval_count", 0),
            eval_count=data.get("eval_count", 0),
        )
        logger.info(
            "[LLM] Response received: %dms, prompt_tokens=%d, eval_tokens=%d",
            result.total_duration_ms, result.prompt_eval_count, result.eval_count,
        )
        return result

    async def is_healthy(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List models available in Ollama."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            if response.status_code != 200:
                return []
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []
