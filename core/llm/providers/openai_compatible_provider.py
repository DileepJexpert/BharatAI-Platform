"""Generic OpenAI-compatible provider for vLLM, LM Studio, LocalAI, etc."""

import logging
import os

import httpx

from core.llm.providers.base import BaseLLMProvider

logger = logging.getLogger("llm.openai_compat")


class OpenAICompatibleProvider(BaseLLMProvider):
    """Works with any OpenAI-compatible API (vLLM, LM Studio, text-generation-inference, LocalAI)."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        api_base: str | None = None,
        api_key: str | None = None,
        models: list[str] | None = None,
    ):
        self._api_base = (api_base or os.getenv("OPENAI_API_BASE", "http://localhost:8080/v1")).rstrip("/")
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._configured_models = models or []
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0),
                headers=headers,
            )
        return self._client

    async def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Standard OpenAI chat completions call."""
        client = self._get_client()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        url = f"{self._api_base}/chat/completions"
        logger.debug("OpenAI-compat request: %s model=%s", url, model)
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def is_healthy(self) -> bool:
        """Check /models endpoint."""
        try:
            client = self._get_client()
            resp = await client.get(f"{self._api_base}/models", timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                # Auto-discover models if not configured
                if not self._configured_models and "data" in data:
                    self._configured_models = [m["id"] for m in data["data"]]
                return True
            return False
        except Exception:
            return False

    def list_models(self) -> list[str]:
        return list(self._configured_models)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
