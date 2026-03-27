"""BasePlugin ABC and PluginRegistry for discovering/loading app plugins."""

import importlib
import logging
import pkgutil
from abc import ABC, abstractmethod
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)


class BasePlugin(ABC):
    """Abstract base class that every app plugin MUST implement."""

    @property
    @abstractmethod
    def app_id(self) -> str:
        """Unique slug: 'asha_health', 'lawyer_ai', etc."""

    @abstractmethod
    def system_prompt(self, language: str, context: dict[str, Any]) -> str:
        """Return domain-specific system prompt.

        Args:
            language: ISO 639-1 code ('hi', 'mr', 'ta', etc.)
            context: session data, user profile, app state
        """

    @abstractmethod
    def parse_response(self, llm_output: str, context: dict[str, Any]) -> dict[str, Any]:
        """Parse LLM output into structured domain object.

        Return dict is stored and returned to client.
        """

    @abstractmethod
    def router(self) -> APIRouter:
        """Return FastAPI router with app-specific routes.

        Core routes (health, voice, chat) are added automatically.
        """

    def on_startup(self) -> None:
        """Optional: called once on platform start."""
        pass

    def on_session_start(self, session: dict[str, Any]) -> dict[str, Any]:
        """Optional: initialise app-specific session state."""
        return session


class PluginLoadError(Exception):
    """Raised when a plugin fails to load."""
    pass


class DuplicatePluginError(Exception):
    """Raised when two plugins register the same app_id."""
    pass


class PluginRegistry:
    """Discovers and loads plugins from the apps/ package."""

    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}

    @property
    def plugins(self) -> dict[str, BasePlugin]:
        """Return all registered plugins keyed by app_id."""
        return dict(self._plugins)

    def get(self, app_id: str) -> BasePlugin | None:
        """Get a plugin by app_id. Returns None if not found."""
        return self._plugins.get(app_id)

    def register(self, plugin: BasePlugin) -> None:
        """Register a single plugin instance.

        Raises:
            PluginLoadError: if plugin doesn't satisfy BasePlugin contract.
            DuplicatePluginError: if app_id is already registered.
        """
        if not isinstance(plugin, BasePlugin):
            raise PluginLoadError(
                f"Plugin {type(plugin).__name__} does not implement BasePlugin"
            )

        app_id = plugin.app_id
        if not app_id or not isinstance(app_id, str):
            raise PluginLoadError(
                f"Plugin {type(plugin).__name__} has invalid app_id: {app_id!r}"
            )

        if app_id in self._plugins:
            raise DuplicatePluginError(
                f"Duplicate app_id '{app_id}': already registered by "
                f"{type(self._plugins[app_id]).__name__}"
            )

        self._plugins[app_id] = plugin
        logger.info("Registered plugin: %s", app_id)

    def discover_and_load(self, apps_package: str = "apps") -> None:
        """Auto-discover plugins from the apps/ package.

        Each app sub-package must have a plugin.py module with a
        `create_plugin() -> BasePlugin` factory function.
        """
        try:
            apps_mod = importlib.import_module(apps_package)
        except ImportError as exc:
            raise PluginLoadError(f"Cannot import apps package '{apps_package}': {exc}")

        for importer, modname, ispkg in pkgutil.iter_modules(
            apps_mod.__path__, prefix=f"{apps_package}."
        ):
            if not ispkg:
                continue

            plugin_module_name = f"{modname}.plugin"
            try:
                plugin_module = importlib.import_module(plugin_module_name)
            except ImportError:
                logger.debug("No plugin.py in %s, skipping", modname)
                continue

            factory = getattr(plugin_module, "create_plugin", None)
            if factory is None:
                logger.warning(
                    "%s has no create_plugin() function, skipping", plugin_module_name
                )
                continue

            try:
                plugin = factory()
                self.register(plugin)
            except Exception as exc:
                logger.error("Failed to load plugin from %s: %s", modname, exc)
                raise PluginLoadError(
                    f"Failed to load plugin from {modname}: {exc}"
                ) from exc

    def startup_all(self) -> None:
        """Call on_startup() for all registered plugins."""
        for app_id, plugin in self._plugins.items():
            try:
                plugin.on_startup()
                logger.info("Plugin %s started", app_id)
            except Exception as exc:
                logger.error("Plugin %s on_startup failed: %s", app_id, exc)
                raise
