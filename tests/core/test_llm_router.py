"""Tests for LLM Router — routing, fallback chain, per-app config.

Test IDs: ROUTER-001 through ROUTER-015
"""

import pytest

from core.llm.providers.base import BaseLLMProvider
from core.llm.router import (
    AppModelConfig,
    FallbackEntry,
    LLMResponse,
    LLMRouter,
    LLMRouterError,
)


# --- Test helpers ---

class MockProvider(BaseLLMProvider):
    """Mock provider for testing."""

    def __init__(self, name: str, models: list[str], fail: bool = False):
        self.provider_name = name
        self._models = models
        self._fail = fail
        self.call_count = 0
        self.last_messages = None

    async def chat(self, messages, model, temperature=0.7, max_tokens=2048):
        self.call_count += 1
        self.last_messages = messages
        if self._fail:
            raise RuntimeError(f"{self.provider_name} is down")
        return f"Response from {self.provider_name}/{model}"

    async def is_healthy(self):
        return not self._fail

    def list_models(self):
        return list(self._models)


def make_router_with_providers():
    """Create router with multiple mock providers."""
    router = LLMRouter()
    router.register_provider(MockProvider("ollama", ["llama3.2"]))
    router.register_provider(MockProvider("groq", ["llama-3.3-70b", "mixtral-8x7b"]))
    router.register_provider(MockProvider("gemini", ["gemini-2.0-flash"]))
    return router


# --- Router tests ---

class TestLLMRouterRegistration:
    """ROUTER-001: Provider registration and config management."""

    def test_register_provider(self):
        router = LLMRouter()
        p = MockProvider("test", ["model-1"])
        router.register_provider(p)
        assert "test" in router.providers

    def test_set_default_config(self):
        router = LLMRouter()
        config = AppModelConfig(provider="groq", model="llama-3.3-70b")
        router.set_default_config(config)
        assert router._default_config == config

    def test_set_app_config(self):
        router = LLMRouter()
        config = AppModelConfig(provider="ollama", model="llama3.2")
        router.set_app_config("asha_health", config)
        assert "asha_health" in router._app_configs

    def test_remove_app_config(self):
        router = LLMRouter()
        config = AppModelConfig(provider="ollama", model="llama3.2")
        router.set_app_config("asha_health", config)
        router.remove_app_config("asha_health")
        assert "asha_health" not in router._app_configs

    def test_get_all_configs(self):
        router = LLMRouter()
        router.set_default_config(AppModelConfig(provider="groq", model="llama-3.3-70b"))
        router.set_app_config("kisanmitra", AppModelConfig(provider="ollama", model="qwen3"))
        configs = router.get_all_configs()
        assert "default" in configs
        assert "kisanmitra" in configs


class TestLLMRouterRouting:
    """ROUTER-002: Request routing to correct provider."""

    @pytest.mark.asyncio
    async def test_routes_to_app_specific_provider(self):
        router = make_router_with_providers()
        router.set_default_config(AppModelConfig(provider="ollama", model="llama3.2"))
        router.set_app_config("kisanmitra", AppModelConfig(provider="groq", model="llama-3.3-70b"))

        result = await router.chat("kisanmitra", [{"role": "user", "content": "hi"}])
        assert result.provider == "groq"
        assert result.model == "llama-3.3-70b"
        assert "groq" in result.text

    @pytest.mark.asyncio
    async def test_falls_back_to_default(self):
        router = make_router_with_providers()
        router.set_default_config(AppModelConfig(provider="ollama", model="llama3.2"))

        result = await router.chat("lawyer_ai", [{"role": "user", "content": "hi"}])
        assert result.provider == "ollama"
        assert result.model == "llama3.2"

    @pytest.mark.asyncio
    async def test_returns_llm_response(self):
        router = make_router_with_providers()
        router.set_default_config(AppModelConfig(provider="ollama", model="llama3.2"))

        result = await router.chat("test", [{"role": "user", "content": "hi"}])
        assert isinstance(result, LLMResponse)
        assert result.text
        assert result.latency_ms >= 0
        assert result.fallback is False


class TestLLMRouterFallback:
    """ROUTER-003: Fallback chain when primary fails."""

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self):
        router = LLMRouter()
        router.register_provider(MockProvider("groq", ["model-a"], fail=True))
        router.register_provider(MockProvider("ollama", ["llama3.2"]))

        config = AppModelConfig(
            provider="groq", model="model-a",
            fallback_chain=[FallbackEntry(provider="ollama", model="llama3.2")],
        )
        router.set_default_config(config)

        result = await router.chat("test", [{"role": "user", "content": "hi"}])
        assert result.provider == "ollama"
        assert result.fallback is True

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises(self):
        router = LLMRouter()
        router.register_provider(MockProvider("groq", ["m"], fail=True))
        router.register_provider(MockProvider("ollama", ["m"], fail=True))

        config = AppModelConfig(
            provider="groq", model="m",
            fallback_chain=[FallbackEntry(provider="ollama", model="m")],
        )
        router.set_default_config(config)

        with pytest.raises(LLMRouterError, match="All providers failed"):
            await router.chat("test", [{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_fallback_chain_tries_in_order(self):
        router = LLMRouter()
        p_primary = MockProvider("primary", ["m"], fail=True)
        p_fallback1 = MockProvider("fallback1", ["m"], fail=True)
        p_fallback2 = MockProvider("fallback2", ["m"], fail=False)
        router.register_provider(p_primary)
        router.register_provider(p_fallback1)
        router.register_provider(p_fallback2)

        config = AppModelConfig(
            provider="primary", model="m",
            fallback_chain=[
                FallbackEntry(provider="fallback1", model="m"),
                FallbackEntry(provider="fallback2", model="m"),
            ],
        )
        router.set_default_config(config)

        result = await router.chat("test", [{"role": "user", "content": "hi"}])
        assert result.provider == "fallback2"
        assert p_primary.call_count == 1
        assert p_fallback1.call_count == 1
        assert p_fallback2.call_count == 1


class TestLLMRouterPerAppRouting:
    """ROUTER-004: Different apps route to different providers."""

    @pytest.mark.asyncio
    async def test_different_apps_different_providers(self):
        router = make_router_with_providers()
        router.set_default_config(AppModelConfig(provider="ollama", model="llama3.2"))
        router.set_app_config("kisanmitra", AppModelConfig(provider="groq", model="llama-3.3-70b"))
        router.set_app_config("vyapaar", AppModelConfig(provider="gemini", model="gemini-2.0-flash"))

        r1 = await router.chat("kisanmitra", [{"role": "user", "content": "hi"}])
        r2 = await router.chat("vyapaar", [{"role": "user", "content": "hi"}])
        r3 = await router.chat("asha_health", [{"role": "user", "content": "hi"}])

        assert r1.provider == "groq"
        assert r2.provider == "gemini"
        assert r3.provider == "ollama"  # uses default


class TestLLMRouterSimpleChat:
    """ROUTER-005: Convenience simple_chat method."""

    @pytest.mark.asyncio
    async def test_simple_chat_builds_messages(self):
        router = LLMRouter()
        mock = MockProvider("ollama", ["llama3.2"])
        router.register_provider(mock)
        router.set_default_config(AppModelConfig(provider="ollama", model="llama3.2"))

        await router.simple_chat("test", "You are helpful", "Hello")
        assert mock.last_messages[0]["role"] == "system"
        assert mock.last_messages[0]["content"] == "You are helpful"
        assert mock.last_messages[1]["role"] == "user"
        assert mock.last_messages[1]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_simple_chat_includes_history(self):
        router = LLMRouter()
        mock = MockProvider("ollama", ["llama3.2"])
        router.register_provider(mock)
        router.set_default_config(AppModelConfig(provider="ollama", model="llama3.2"))

        history = [
            {"role": "user", "text": "prev question"},
            {"role": "assistant", "text": "prev answer"},
        ]
        await router.simple_chat("test", "System", "New question", conversation_history=history)
        assert len(mock.last_messages) == 4  # system + 2 history + user


class TestLLMRouterTestProvider:
    """ROUTER-006: Testing providers before assignment."""

    @pytest.mark.asyncio
    async def test_test_provider_success(self):
        router = LLMRouter()
        router.register_provider(MockProvider("groq", ["llama-3.3-70b"]))

        result = await router.test_provider("groq", "llama-3.3-70b")
        assert result["status"] == "success"
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_test_provider_failure(self):
        router = LLMRouter()
        router.register_provider(MockProvider("groq", ["m"], fail=True))

        result = await router.test_provider("groq", "m")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_test_unregistered_provider(self):
        router = LLMRouter()
        result = await router.test_provider("nonexistent", "m")
        assert result["status"] == "error"
        assert "not registered" in result["message"]


class TestLLMRouterConfigChangeNoRestart:
    """ROUTER-007: Config changes take effect immediately."""

    @pytest.mark.asyncio
    async def test_config_change_immediate_effect(self):
        router = make_router_with_providers()
        router.set_default_config(AppModelConfig(provider="ollama", model="llama3.2"))

        # First call goes to Ollama (default)
        r1 = await router.chat("kisanmitra", [{"role": "user", "content": "hi"}])
        assert r1.provider == "ollama"

        # Change config at runtime — no restart
        router.set_app_config("kisanmitra", AppModelConfig(provider="groq", model="llama-3.3-70b"))

        # Next call goes to Groq immediately
        r2 = await router.chat("kisanmitra", [{"role": "user", "content": "hi"}])
        assert r2.provider == "groq"


class TestAppModelConfig:
    """ROUTER-008: AppModelConfig serialization."""

    def test_to_dict(self):
        config = AppModelConfig(
            provider="groq", model="llama-3.3-70b",
            fallback_chain=[FallbackEntry(provider="ollama", model="llama3.2")],
        )
        d = config.to_dict()
        assert d["provider"] == "groq"
        assert d["model"] == "llama-3.3-70b"
        assert len(d["fallback_chain"]) == 1

    def test_from_dict(self):
        data = {
            "provider": "gemini",
            "model": "gemini-2.0-flash",
            "temperature": 0.5,
            "max_tokens": 1024,
            "fallback_chain": [{"provider": "ollama", "model": "qwen3"}],
        }
        config = AppModelConfig.from_dict(data)
        assert config.provider == "gemini"
        assert config.temperature == 0.5
        assert len(config.fallback_chain) == 1
        assert config.fallback_chain[0].provider == "ollama"

    def test_roundtrip(self):
        original = AppModelConfig(
            provider="claude", model="claude-sonnet-4-20250514",
            temperature=0.3, max_tokens=4096,
            fallback_chain=[
                FallbackEntry(provider="groq", model="llama-3.3-70b"),
                FallbackEntry(provider="ollama", model="llama3.2"),
            ],
        )
        restored = AppModelConfig.from_dict(original.to_dict())
        assert restored.provider == original.provider
        assert restored.model == original.model
        assert restored.temperature == original.temperature
        assert len(restored.fallback_chain) == 2
