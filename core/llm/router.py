"""LLM Router — routes requests to the correct provider based on app_id config."""

import logging
import time
from dataclasses import dataclass, field

from core.llm.providers.base import BaseLLMProvider

logger = logging.getLogger("llm.router")


@dataclass
class FallbackEntry:
    """A single entry in a fallback chain."""
    provider: str
    model: str


@dataclass
class AppModelConfig:
    """Per-app LLM configuration."""
    provider: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 2048
    fallback_chain: list[FallbackEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "fallback_chain": [
                {"provider": f.provider, "model": f.model} for f in self.fallback_chain
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppModelConfig":
        chain = [
            FallbackEntry(provider=f["provider"], model=f["model"])
            for f in data.get("fallback_chain", [])
        ]
        return cls(
            provider=data["provider"],
            model=data["model"],
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 2048),
            fallback_chain=chain,
        )


@dataclass
class LLMResponse:
    """Response from the LLM router."""
    text: str
    provider: str
    model: str
    fallback: bool = False
    latency_ms: int = 0
    tokens_used: int = 0


class LLMRouterError(Exception):
    """All providers failed."""


class LLMRouter:
    """Routes LLM requests to the correct provider based on app_id config."""

    def __init__(self) -> None:
        self.providers: dict[str, BaseLLMProvider] = {}
        self._app_configs: dict[str, AppModelConfig] = {}
        self._default_config: AppModelConfig | None = None

    def register_provider(self, provider: BaseLLMProvider) -> None:
        """Register a provider instance (called on startup)."""
        self.providers[provider.provider_name] = provider
        logger.info("Registered LLM provider: %s", provider.provider_name)

    def set_default_config(self, config: AppModelConfig) -> None:
        """Set the default config used when no app-specific config exists."""
        self._default_config = config
        logger.info("Default LLM config: %s/%s", config.provider, config.model)

    def set_app_config(self, app_id: str, config: AppModelConfig) -> None:
        """Set which provider+model to use for a specific app. Takes effect immediately."""
        self._app_configs[app_id] = config
        logger.info(
            "App '%s' LLM config: %s/%s (fallbacks: %d)",
            app_id, config.provider, config.model, len(config.fallback_chain),
        )

    def remove_app_config(self, app_id: str) -> None:
        """Remove app-specific config, reverting to default."""
        self._app_configs.pop(app_id, None)

    def get_app_config(self, app_id: str) -> AppModelConfig:
        """Get config for an app. Falls back to default if not set."""
        config = self._app_configs.get(app_id)
        if config:
            return config
        if self._default_config:
            return self._default_config
        # Ultimate fallback — first registered provider
        if self.providers:
            first_provider = next(iter(self.providers.values()))
            models = first_provider.list_models()
            return AppModelConfig(
                provider=first_provider.provider_name,
                model=models[0] if models else "default",
            )
        raise LLMRouterError("No providers registered and no default config set")

    def get_all_configs(self) -> dict[str, dict]:
        """Return all app configs as dicts (for admin dashboard)."""
        result: dict[str, dict] = {}
        if self._default_config:
            result["default"] = self._default_config.to_dict()
        for app_id, config in self._app_configs.items():
            result[app_id] = config.to_dict()
        return result

    async def chat(
        self,
        app_id: str,
        messages: list[dict],
        **kwargs,
    ) -> LLMResponse:
        """Route chat to correct provider. Handle fallback chain on failure."""
        config = self.get_app_config(app_id)
        temperature = kwargs.pop("temperature", config.temperature)
        max_tokens = kwargs.pop("max_tokens", config.max_tokens)

        # Try primary provider
        start = time.monotonic()
        provider = self.providers.get(config.provider)
        if provider:
            try:
                text = await provider.chat(
                    messages, config.model,
                    temperature=temperature, max_tokens=max_tokens,
                )
                latency = int((time.monotonic() - start) * 1000)
                return LLMResponse(
                    text=text, provider=config.provider,
                    model=config.model, latency_ms=latency,
                )
            except Exception as e:
                logger.warning("Primary LLM failed for %s (%s/%s): %s", app_id, config.provider, config.model, e)
        else:
            logger.warning("Provider '%s' not registered for app '%s'", config.provider, app_id)

        # Try fallback chain
        for fb in config.fallback_chain:
            fb_provider = self.providers.get(fb.provider)
            if not fb_provider:
                continue
            try:
                start = time.monotonic()
                text = await fb_provider.chat(
                    messages, fb.model,
                    temperature=temperature, max_tokens=max_tokens,
                )
                latency = int((time.monotonic() - start) * 1000)
                logger.info("Fallback succeeded: %s/%s for app %s", fb.provider, fb.model, app_id)
                return LLMResponse(
                    text=text, provider=fb.provider,
                    model=fb.model, fallback=True, latency_ms=latency,
                )
            except Exception as e:
                logger.warning("Fallback %s/%s failed: %s", fb.provider, fb.model, e)

        raise LLMRouterError(f"All providers failed for app: {app_id}")

    async def simple_chat(
        self,
        app_id: str,
        system_prompt: str,
        user_text: str,
        conversation_history: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Convenience wrapper that builds messages from system + user + history."""
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            for turn in conversation_history[-10:]:
                role = turn.get("role", "user")
                content = turn.get("text", turn.get("content", ""))
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_text})
        return await self.chat(app_id, messages, **kwargs)

    async def test_provider(
        self,
        provider_name: str,
        model: str,
        test_message: str = "Hello, respond in one sentence.",
    ) -> dict:
        """Test a specific provider+model combination. Returns status dict."""
        provider = self.providers.get(provider_name)
        if not provider:
            return {"status": "error", "message": f"Provider '{provider_name}' not registered"}

        messages = [{"role": "user", "content": test_message}]
        start = time.monotonic()
        try:
            text = await provider.chat(messages, model)
            latency = int((time.monotonic() - start) * 1000)
            return {
                "status": "success",
                "response": text,
                "latency_ms": latency,
                "provider": provider_name,
                "model": model,
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "provider": provider_name, "model": model}

    async def get_provider_status(self) -> list[dict]:
        """Get health status of all registered providers."""
        results = []
        for name, provider in self.providers.items():
            healthy = await provider.is_healthy()
            results.append({
                "name": name,
                "status": "healthy" if healthy else "unhealthy",
                "models": provider.list_models(),
                "is_local": name in ("ollama", "openai_compatible"),
            })
        return results

    async def close(self) -> None:
        """Close all provider connections."""
        for provider in self.providers.values():
            await provider.close()
