"""FastAPI application — route registration, plugin loading, core endpoints."""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.api.plugin_registry import PluginRegistry
from core.auth.middleware import AuthMiddleware
from core.llm.model_manager import ModelManager

logger = logging.getLogger(__name__)

# Module-level singletons
registry = PluginRegistry()
model_manager = ModelManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    # Startup
    logger.info("BharatAI Platform starting...")

    # Discover and load plugins
    try:
        registry.discover_and_load("apps")
        registry.startup_all()
        logger.info("Loaded plugins: %s", list(registry.plugins.keys()))
    except Exception as exc:
        logger.warning("Plugin loading: %s", exc)

    # Load default LLM model
    try:
        model_manager.load()
        logger.info("Default model loaded: %s", model_manager.active_model)
    except Exception as exc:
        logger.warning("Model load deferred: %s", exc)

    yield

    # Shutdown
    logger.info("BharatAI Platform shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="BharatAI Platform",
        description="Shared AI backend for Indian-language applications",
        version="1.0.0-mvp",
        lifespan=lifespan,
    )

    # Add auth middleware
    app.add_middleware(AuthMiddleware)

    # Register core routes
    _register_core_routes(app)

    # Register plugin routes
    _register_plugin_routes(app)

    return app


def _register_core_routes(app: FastAPI) -> None:
    """Register platform-wide routes."""

    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        """Platform health check with model status."""
        return {
            "status": "healthy",
            "platform": "BharatAI",
            "version": "1.0.0-mvp",
            "plugins_loaded": list(registry.plugins.keys()),
            "model_status": model_manager.status(),
        }

    @app.get("/models")
    async def list_models() -> dict[str, Any]:
        """List loaded models and VRAM usage."""
        return model_manager.status()

    @app.post("/admin/load-model")
    async def load_model(request: Request) -> dict[str, Any]:
        """Load a specific model into VRAM (admin only)."""
        body = await request.json()
        model_key = body.get("model_key")
        if not model_key:
            return JSONResponse(
                status_code=400,
                content={"detail": "model_key is required"},
            )

        try:
            status = model_manager.load(model_key)
            return {
                "message": f"Model '{model_key}' loaded",
                "status": {
                    "model_key": status.model_key,
                    "ollama_tag": status.ollama_tag,
                    "vram_mb": status.vram_mb,
                },
            }
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content={"detail": str(exc)},
            )


def _register_plugin_routes(app: FastAPI) -> None:
    """Register each plugin's router under /{app_id}/ prefix."""
    for app_id, plugin in registry.plugins.items():
        try:
            router = plugin.router()
            app.include_router(router, prefix=f"/{app_id}", tags=[app_id])
            logger.info("Registered routes for plugin: %s", app_id)
        except Exception as exc:
            logger.error("Failed to register routes for %s: %s", app_id, exc)


# Create the app instance
app = create_app()
