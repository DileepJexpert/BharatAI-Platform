"""Google Gemini provider — REST API via httpx."""

import logging
import os

import httpx

from core.llm.providers.base import BaseLLMProvider

logger = logging.getLogger("llm.gemini")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]


class GeminiProvider(BaseLLMProvider):
    """Google Gemini via REST API (free tier: 15 req/min for flash)."""

    provider_name = "gemini"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client

    def _convert_messages(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Convert OpenAI-style messages to Gemini format.

        Returns (system_instruction, contents).
        """
        system_text = None
        contents: list[dict] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_text = content
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})

        return system_text, contents

    async def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Send generateContent request to Gemini."""
        client = self._get_client()
        system_text, contents = self._convert_messages(messages)

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}

        url = f"{GEMINI_BASE_URL}/models/{model}:generateContent?key={self._api_key}"
        logger.debug("Gemini request: model=%s contents=%d", model, len(contents))
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates: {data}")

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        return text

    async def is_healthy(self) -> bool:
        """Check Gemini API with a lightweight models list call."""
        if not self._api_key:
            return False
        try:
            client = self._get_client()
            url = f"{GEMINI_BASE_URL}/models?key={self._api_key}&pageSize=1"
            resp = await client.get(url, timeout=10.0)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        return list(GEMINI_MODELS)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
