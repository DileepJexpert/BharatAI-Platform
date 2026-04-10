"""Groq provider — fast cloud inference via OpenAI-compatible API."""

import asyncio
import logging
import os

import httpx

from core.llm.providers.base import BaseLLMProvider

logger = logging.getLogger("llm.groq")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]
MAX_RETRIES = 3
BASE_RETRY_DELAY = 2.0


class GroqProvider(BaseLLMProvider):
    """Groq cloud inference (free tier: 30 req/min)."""

    provider_name = "groq"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("GROQ_API_KEY", "")
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
        """Send chat request with retry on 429 rate limits."""
        client = self._get_client()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.post(GROQ_API_URL, json=payload)
                if resp.status_code == 429:
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    logger.warning("Groq rate limited, retrying in %.1fs (attempt %d)", delay, attempt + 1)
                    await asyncio.sleep(delay)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code != 429:
                    raise
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BASE_RETRY_DELAY * (2 ** attempt))
                    continue
                raise

        raise RuntimeError(f"Groq request failed after {MAX_RETRIES} retries: {last_error}")

    async def is_healthy(self) -> bool:
        """Check Groq API reachability."""
        if not self._api_key:
            return False
        try:
            client = self._get_client()
            resp = await client.get(
                "https://api.groq.com/openai/v1/models",
                timeout=10.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        return list(GROQ_MODELS)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
