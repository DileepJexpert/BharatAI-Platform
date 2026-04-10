"""Tests for ModelConfigStore — in-memory and Redis persistence.

Test IDs: CFGSTORE-001 through CFGSTORE-010
"""

import pytest

from core.llm.config_store import ModelConfigStore
from core.llm.router import AppModelConfig, FallbackEntry, LLMRouter


class TestModelConfigStoreInMemory:
    """CFGSTORE-001: Config store works with in-memory fallback (no Redis/DB)."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        store = ModelConfigStore()
        config = AppModelConfig(provider="groq", model="llama-3.3-70b")
        await store.set_app_config("kisanmitra", config)

        result = await store.get_app_config("kisanmitra")
        assert result is not None
        assert result.provider == "groq"
        assert result.model == "llama-3.3-70b"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self):
        store = ModelConfigStore()
        result = await store.get_app_config("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_configs(self):
        store = ModelConfigStore()
        await store.set_app_config("app1", AppModelConfig(provider="groq", model="m1"))
        await store.set_app_config("app2", AppModelConfig(provider="gemini", model="m2"))

        all_configs = await store.get_all_configs()
        assert "app1" in all_configs
        assert "app2" in all_configs
        assert all_configs["app1"].provider == "groq"
        assert all_configs["app2"].provider == "gemini"

    @pytest.mark.asyncio
    async def test_delete_config(self):
        store = ModelConfigStore()
        await store.set_app_config("app1", AppModelConfig(provider="groq", model="m1"))
        await store.delete_app_config("app1")

        result = await store.get_app_config("app1")
        assert result is None

    @pytest.mark.asyncio
    async def test_overwrite_config(self):
        store = ModelConfigStore()
        await store.set_app_config("app1", AppModelConfig(provider="groq", model="old"))
        await store.set_app_config("app1", AppModelConfig(provider="gemini", model="new"))

        result = await store.get_app_config("app1")
        assert result.provider == "gemini"
        assert result.model == "new"


class TestModelConfigStoreDefault:
    """CFGSTORE-002: Default config from environment."""

    def test_get_default_config(self):
        store = ModelConfigStore()
        config = store.get_default_config()
        assert config.provider  # Should have some provider
        assert config.model  # Should have some model
        assert config.temperature == 0.7
        assert config.max_tokens == 2048


class TestModelConfigStoreWithFallback:
    """CFGSTORE-003: Configs with fallback chains."""

    @pytest.mark.asyncio
    async def test_save_and_load_with_fallback(self):
        store = ModelConfigStore()
        config = AppModelConfig(
            provider="groq", model="llama-3.3-70b",
            fallback_chain=[
                FallbackEntry(provider="gemini", model="gemini-2.0-flash"),
                FallbackEntry(provider="ollama", model="llama3.2"),
            ],
        )
        await store.set_app_config("kisanmitra", config)

        result = await store.get_app_config("kisanmitra")
        assert len(result.fallback_chain) == 2
        assert result.fallback_chain[0].provider == "gemini"
        assert result.fallback_chain[1].provider == "ollama"


class TestModelConfigStoreRouterIntegration:
    """CFGSTORE-004: Loading configs into router."""

    @pytest.mark.asyncio
    async def test_load_all_to_router(self):
        store = ModelConfigStore()
        await store.set_app_config("default", AppModelConfig(provider="groq", model="llama-3.3-70b"))
        await store.set_app_config("kisanmitra", AppModelConfig(provider="ollama", model="qwen3"))

        router = LLMRouter()
        await store.load_all_to_router(router)

        assert router._default_config is not None
        assert router._default_config.provider == "groq"
        assert "kisanmitra" in router._app_configs
        assert router._app_configs["kisanmitra"].provider == "ollama"
