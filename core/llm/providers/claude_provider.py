"""Anthropic Claude provider — Messages API via httpx."""

import logging
import os

import httpx

from core.llm.providers.base import BaseLLMProvider

logger = logging.getLogger("llm.claude")

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODELS = ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"]
ANTHROPIC_VERSION = "2023-06-01"


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude via Messages API (paid)."""

    provider_name = "claude"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(90.0, connect=10.0),
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
            )
        return self._client

    def _convert_messages(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Split system message from conversation messages.

        Claude expects system as a top-level param, not in messages.
        """
        system_text = None
        converted: list[dict] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_text = content
            else:
                converted.append({"role": role, "content": content})

        return system_text, converted

    async def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Send Messages API request to Claude."""
        client = self._get_client()
        system_text, conv_messages = self._convert_messages(messages)

        payload: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": conv_messages,
            "temperature": temperature,
        }
        if system_text:
            payload["system"] = system_text

        logger.debug("Claude request: model=%s messages=%d", model, len(conv_messages))
        resp = await client.post(CLAUDE_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

        content_blocks = data.get("content", [])
        text = "".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        )
        return text

    async def is_healthy(self) -> bool:
        """Check if API key is valid. Claude has no lightweight ping endpoint."""
        if not self._api_key:
            return False
        try:
            client = self._get_client()
            # Send a minimal request to check auth
            resp = await client.post(
                CLAUDE_API_URL,
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
                timeout=15.0,
            )
            # 200 = working, 401 = bad key, 429 = rate limited but key valid
            return resp.status_code in (200, 429)
        except Exception:
            return False

    def list_models(self) -> list[str]:
        return list(CLAUDE_MODELS)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
