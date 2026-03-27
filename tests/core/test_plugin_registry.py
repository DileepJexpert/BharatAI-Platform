"""Tests for core/api/plugin_registry.py — plugin loading and registration."""

import pytest
from unittest.mock import MagicMock

from fastapi import APIRouter

from core.api.plugin_registry import (
    BasePlugin,
    PluginRegistry,
    PluginLoadError,
    DuplicatePluginError,
)


class MockPlugin(BasePlugin):
    """Valid mock plugin for testing."""

    def __init__(self, app_id_val: str = "test_app"):
        self._app_id = app_id_val

    @property
    def app_id(self) -> str:
        return self._app_id

    def system_prompt(self, language: str, context: dict) -> str:
        return f"Test prompt in {language}"

    def parse_response(self, llm_output: str, context: dict) -> dict:
        return {"raw": llm_output}

    def router(self) -> APIRouter:
        return APIRouter()


class TestPluginRegistration:
    def test_register_valid_plugin(self):
        registry = PluginRegistry()
        plugin = MockPlugin("my_app")
        registry.register(plugin)
        assert registry.get("my_app") is plugin

    def test_register_duplicate_raises(self):
        registry = PluginRegistry()
        registry.register(MockPlugin("dup_app"))
        with pytest.raises(DuplicatePluginError, match="dup_app"):
            registry.register(MockPlugin("dup_app"))

    def test_register_non_plugin_raises(self):
        registry = PluginRegistry()
        with pytest.raises(PluginLoadError, match="does not implement"):
            registry.register("not a plugin")  # type: ignore

    def test_get_nonexistent_returns_none(self):
        registry = PluginRegistry()
        assert registry.get("nonexistent") is None

    def test_plugins_property(self):
        registry = PluginRegistry()
        registry.register(MockPlugin("app_a"))
        registry.register(MockPlugin("app_b"))
        plugins = registry.plugins
        assert len(plugins) == 2
        assert "app_a" in plugins
        assert "app_b" in plugins

    def test_startup_all(self):
        registry = PluginRegistry()
        plugin = MockPlugin("startup_test")
        plugin.on_startup = MagicMock()
        registry.register(plugin)
        registry.startup_all()
        plugin.on_startup.assert_called_once()


class TestPluginContract:
    """Verify BasePlugin ABC enforces the contract."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            BasePlugin()  # type: ignore

    def test_must_implement_all_methods(self):
        class IncompletePlugin(BasePlugin):
            @property
            def app_id(self) -> str:
                return "incomplete"

        with pytest.raises(TypeError):
            IncompletePlugin()  # type: ignore
