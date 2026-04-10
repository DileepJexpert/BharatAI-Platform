"""Sarvam AI provider — Hindi-optimized LLM."""

import logging
import os

import httpx

from core.llm.providers.base import BaseLLMProvider

logger = logging.getLogger("llm.sarvam")

SARVAM_API_URL = "https://api.sarvam.ai/v1/chat/completions"
SARVAM_MODELS = ["sarvam-2b-v0.5"]


class SarvamProvider(BaseLLMProvider):
    """Sarvam AI — best for Hindi-specific tasks."""

    provider_name = "sarvam"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("SARVAM_API_KEY", "")
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Send OpenAI-compatible chat request to Sarvam."""
        client = self._get_client()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        logger.debug("Sarvam request: model=%s messages=%d", model, len(messages))
        resp = await client.post(SARVAM_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def is_healthy(self) -> bool:
        """Check Sarvam API reachability."""
        if not self._api_key:
            return False
        try:
            client = self._get_client()
            resp = await client.get(
                "https://api.sarvam.ai/v1/models",
                timeout=10.0,
            )
            return resp.status_code in (200, 404)  # 404 is valid (endpoint may not exist)
        except Exception:
            return False

    def list_models(self) -> list[str]:
        return list(SARVAM_MODELS)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
