"""Admin API endpoints for multi-provider LLM management."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from core.llm.config_store import ModelConfigStore
from core.llm.router import AppModelConfig, FallbackEntry, LLMRouter

logger = logging.getLogger("admin.llm")


def create_admin_llm_router(llm_router: LLMRouter, config_store: ModelConfigStore) -> APIRouter:
    """Create FastAPI router for LLM admin endpoints."""

    router = APIRouter(prefix="/admin/llm", tags=["admin-llm"])

    @router.get("/providers")
    async def list_providers() -> dict[str, Any]:
        """List all registered providers with health status and available models."""
        providers = await llm_router.get_provider_status()
        return {"providers": providers}

    @router.get("/config")
    async def get_all_config() -> dict[str, Any]:
        """Get current model config for all apps."""
        # Get configs from the router (in-memory state)
        configs = llm_router.get_all_configs()

        # Get known plugin IDs
        from core.api.gateway import registry
        plugin_ids = list(registry.plugins.keys())

        result: dict[str, Any] = {}
        if "default" in configs:
            result["default"] = configs["default"]

        for app_id in plugin_ids:
            if app_id in configs:
                result[app_id] = configs[app_id]
            else:
                result[app_id] = None  # Using default

        return result

    @router.put("/config/{app_id}")
    async def set_app_config(app_id: str, request: Request) -> dict[str, Any]:
        """Set LLM config for a specific app. Takes effect IMMEDIATELY."""
        body = await request.json()

        provider = body.get("provider")
        model = body.get("model")
        if not provider or not model:
            raise HTTPException(400, "Both 'provider' and 'model' are required")

        # Validate provider exists
        if provider not in llm_router.providers:
            available = list(llm_router.providers.keys())
            raise HTTPException(400, f"Unknown provider '{provider}'. Available: {available}")

        # Validate model is available
        available_models = llm_router.providers[provider].list_models()
        if available_models and model not in available_models:
            logger.warning("Model '%s' not in known list for %s, allowing anyway", model, provider)

        # Build fallback chain
        fallback_chain = []
        for fb in body.get("fallback_chain", []):
            if "provider" in fb and "model" in fb:
                fallback_chain.append(FallbackEntry(provider=fb["provider"], model=fb["model"]))

        config = AppModelConfig(
            provider=provider,
            model=model,
            temperature=body.get("temperature", 0.7),
            max_tokens=body.get("max_tokens", 2048),
            fallback_chain=fallback_chain,
        )

        # Update router (immediate effect)
        if app_id == "default":
            llm_router.set_default_config(config)
        else:
            llm_router.set_app_config(app_id, config)

        # Persist to config store
        await config_store.set_app_config(app_id, config)

        logger.info("LLM config updated for '%s': %s/%s (immediate)", app_id, provider, model)
        return {
            "message": "Updated",
            "app_id": app_id,
            "effective": "immediate",
            "config": config.to_dict(),
        }

    @router.delete("/config/{app_id}")
    async def delete_app_config(app_id: str) -> dict[str, str]:
        """Remove app-specific config, reverting to default."""
        if app_id == "default":
            raise HTTPException(400, "Cannot delete default config")

        llm_router.remove_app_config(app_id)
        await config_store.delete_app_config(app_id)
        return {"message": f"Config for '{app_id}' removed, now using default"}

    @router.post("/test")
    async def test_provider(request: Request) -> dict[str, Any]:
        """Test a specific provider+model combination before assigning to an app."""
        body = await request.json()
        provider_name = body.get("provider")
        model = body.get("model")
        test_message = body.get("test_message", "Namaste, respond in one short sentence.")

        if not provider_name or not model:
            raise HTTPException(400, "'provider' and 'model' are required")

        result = await llm_router.test_provider(provider_name, model, test_message)
        return result

    return router
