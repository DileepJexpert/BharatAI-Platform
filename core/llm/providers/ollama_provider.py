"""Ollama provider — wraps the local Ollama server."""

import logging
import os

import httpx

from core.llm.providers.base import BaseLLMProvider

logger = logging.getLogger("llm.ollama")

OLLAMA_HOST = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))


class OllamaProvider(BaseLLMProvider):
    """Local Ollama inference server."""

    provider_name = "ollama"

    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self._base_url = (base_url or OLLAMA_HOST).rstrip("/")
        self._timeout = timeout or OLLAMA_TIMEOUT
        self._client: httpx.AsyncClient | None = None
        self._cached_models: list[str] = []

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout, connect=10.0),
            )
        return self._client

    async def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Send chat request to Ollama /api/chat endpoint."""
        client = self._get_client()
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        logger.debug("Ollama request: model=%s messages=%d", model, len(messages))
        resp = await client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("message", {}).get("content", "")
        logger.debug("Ollama response: %d chars, model=%s", len(text), model)
        return text

    async def generate(self, prompt: str, model: str, **kwargs) -> str:
        """Raw completion via /api/generate (non-chat)."""
        client = self._get_client()
        payload = {"model": model, "prompt": prompt, "stream": False, **kwargs}
        resp = await client.post("/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "")

    async def is_healthy(self) -> bool:
        """Check Ollama connectivity via /api/tags."""
        try:
            client = self._get_client()
            resp = await client.get("/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """Return cached model list. Call refresh_models() to update."""
        return list(self._cached_models)

    async def refresh_models(self) -> list[str]:
        """Fetch available models from Ollama and cache them."""
        try:
            client = self._get_client()
            resp = await client.get("/api/tags", timeout=10.0)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            self._cached_models = models
            return models
        except Exception as e:
            logger.warning("Failed to refresh Ollama models: %s", e)
            return self._cached_models

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
