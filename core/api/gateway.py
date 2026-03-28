"""FastAPI application — route registration, plugin loading, core endpoints."""

import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

# Configure logging to show everything in console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.api.plugin_registry import PluginRegistry
from core.auth.middleware import AuthMiddleware
from core.llm.client import OllamaClient
from core.llm.model_manager import ModelManager
from core.voice.models import ChatRequest, ChatResponse, VoiceResponse
from core.voice.pipeline import VoicePipeline
from core.voice.session_store import SessionStore
from core.voice.stt import STTService
from core.voice.tts import TTSService

logger = logging.getLogger("gateway")

# Module-level singletons
registry = PluginRegistry()
model_manager = ModelManager()
stt_service = STTService()
tts_service = TTSService()
ollama_client = OllamaClient()
session_store = SessionStore()
pipeline: VoicePipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    global pipeline

    logger.info("=" * 60)
    logger.info("  BHARATAI PLATFORM STARTING UP")
    logger.info("=" * 60)

    # Discover and load plugins
    try:
        logger.info("[STARTUP] Discovering plugins in 'apps/' folder...")
        registry.discover_and_load("apps")
        registry.startup_all()
        logger.info("[STARTUP] Plugins loaded: %s", list(registry.plugins.keys()))
    except Exception as exc:
        logger.warning("[STARTUP] Plugin loading warning: %s", exc)

    # Load default LLM model
    try:
        logger.info("[STARTUP] Loading default LLM model configuration...")
        model_manager.load()
        logger.info("[STARTUP] Default model set: %s", model_manager.active_model)
    except Exception as exc:
        logger.warning("[STARTUP] Model load deferred: %s", exc)

    # Create voice pipeline
    logger.info("[STARTUP] Creating voice pipeline (STT + LLM + TTS)...")
    pipeline = VoicePipeline(
        stt=stt_service,
        tts=tts_service,
        llm=ollama_client,
        model_manager=model_manager,
        registry=registry,
        session_store=session_store,
    )

    logger.info("[STARTUP] Ollama URL: %s", ollama_client.base_url)
    logger.info("[STARTUP] Redis URL: %s", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    logger.info("=" * 60)
    logger.info("  BHARATAI PLATFORM READY — http://localhost:8000")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("[SHUTDOWN] BharatAI Platform shutting down...")
    await ollama_client.close()
    await session_store.close()
    logger.info("[SHUTDOWN] Cleanup complete.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="BharatAI Platform",
        description="Shared AI backend for Indian-language applications",
        version="1.0.0-mvp",
        lifespan=lifespan,
    )

    # Add CORS middleware (must be added before auth)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add auth middleware
    app.add_middleware(AuthMiddleware)

    # Register core routes
    _register_core_routes(app)

    # Register WhatsApp webhook
    from core.integrations.whatsapp import router as whatsapp_router
    app.include_router(whatsapp_router)

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

    # --- Voice endpoint (core — works for any registered plugin) ---

    @app.post("/{app_id}/voice")
    async def voice_endpoint(
        app_id: str,
        audio: UploadFile = File(...),
        session_id: str = Form(default=""),
        language_hint: str = Form(default=""),
    ) -> dict[str, Any]:
        """Upload audio, get text + audio response."""
        logger.info("[ROUTE] POST /%s/voice — audio upload received", app_id)
        if pipeline is None:
            raise HTTPException(503, "Pipeline not initialized")

        if not session_id:
            session_id = str(uuid.uuid4())

        audio_bytes = await audio.read()
        logger.info("[ROUTE] Audio size: %d bytes, session=%s", len(audio_bytes), session_id)

        # Check audio size
        max_size = 10 * 1024 * 1024  # 10MB
        if len(audio_bytes) > max_size:
            raise HTTPException(413, "Audio file too large. Maximum size is 10MB.")

        result = await pipeline.process(
            audio=audio_bytes,
            app_id=app_id,
            session_id=session_id,
            language_hint=language_hint or None,
        )

        response = _voice_response_to_dict(result, session_id)
        logger.info("[ROUTE] Voice response: error=%s, processing_ms=%s", response.get("error"), response.get("processing_ms"))
        return response

    # --- Chat endpoint (text-only) ---

    @app.post("/{app_id}/chat")
    async def chat_endpoint(app_id: str, request: ChatRequest) -> dict[str, Any]:
        """Text-only input, returns text response."""
        logger.info("[ROUTE] >>> POST /%s/chat — text: '%s'", app_id, request.text[:100])
        logger.info("[ROUTE] Session: %s, Language hint: %s", request.session_id, request.language_hint)
        if pipeline is None:
            raise HTTPException(503, "Pipeline not initialized")

        result = await pipeline.process_text(
            text=request.text,
            app_id=app_id,
            session_id=request.session_id,
            language_hint=request.language_hint,
        )

        response = _voice_response_to_dict(result, request.session_id)
        logger.info("[ROUTE] <<< Chat response: error=%s, processing_ms=%s", response.get("error"), response.get("processing_ms"))
        return response

    # --- Session endpoints ---

    @app.get("/{app_id}/session/{session_id}")
    async def get_session(app_id: str, session_id: str) -> dict[str, Any]:
        """Fetch current session state."""
        session = await session_store.get(session_id)
        if session is None:
            raise HTTPException(404, "Session not found")
        if session.get("app_id") != app_id:
            raise HTTPException(403, "Session belongs to a different app")
        return session

    @app.delete("/{app_id}/session/{session_id}")
    async def delete_session(app_id: str, session_id: str) -> dict[str, str]:
        """Clear session. User starts fresh conversation."""
        await session_store.delete(session_id)
        return {"message": "Session deleted", "session_id": session_id}


def _voice_response_to_dict(result: VoiceResponse, session_id: str) -> dict[str, Any]:
    """Convert VoiceResponse to API dict, excluding raw audio bytes."""
    return {
        "session_id": result.session_id or session_id,
        "transcript": result.transcript,
        "language": result.language,
        "response_text": result.response_text,
        "response_audio_url": None,  # TODO: store audio and return URL
        "domain_data": result.domain_data,
        "confidence": result.confidence,
        "processing_ms": result.processing_ms,
        "error": result.error,
    }


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
