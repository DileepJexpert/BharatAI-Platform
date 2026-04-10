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
from core.llm.config_store import ModelConfigStore
from core.llm.model_manager import ModelManager
from core.llm.router import AppModelConfig, LLMRouter
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
llm_router = LLMRouter()
config_store = ModelConfigStore()
pipeline: VoicePipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    global pipeline

    logger.info("=" * 60)
    logger.info("  BHARATAI PLATFORM STARTING UP")
    logger.info("=" * 60)

    # --- Init Database (optional — works without it) ---
    db_available = False
    try:
        from core.db.base import init_db
        logger.info("[STARTUP] Connecting to PostgreSQL...")
        await init_db()
        db_available = True
        logger.info("[STARTUP] PostgreSQL connected")
    except Exception as exc:
        logger.warning("[STARTUP] PostgreSQL not available: %s", exc)
        logger.warning("[STARTUP] Running without database — using in-memory storage")

    # --- Check Redis (optional — falls back to in-memory) ---
    redis_available = False
    try:
        logger.info("[STARTUP] Checking Redis connection...")
        test_session = await session_store._get_redis()
        await test_session.ping()
        redis_available = True
        logger.info("[STARTUP] Redis connected")
    except Exception as exc:
        logger.warning("[STARTUP] Redis not available: %s", exc)
        logger.warning("[STARTUP] Running without Redis — sessions will use in-memory store")

    # --- Check Ollama ---
    ollama_available = False
    try:
        logger.info("[STARTUP] Checking Ollama connection...")
        ollama_available = await ollama_client.is_healthy()
        if ollama_available:
            models = await ollama_client.list_models()
            logger.info("[STARTUP] Ollama connected — models available: %s", models)
        else:
            logger.warning("[STARTUP] Ollama not responding at %s", ollama_client.base_url)
    except Exception as exc:
        logger.warning("[STARTUP] Ollama check failed: %s", exc)

    # --- Register LLM Providers ---
    logger.info("[STARTUP] Registering LLM providers...")
    await _register_llm_providers(ollama_available)

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

    # --- Init ChromaDB (optional — RAG unavailable without it) ---
    chroma_available = False
    try:
        from core.db.chroma_client import ChromaClient
        chroma_client = ChromaClient()
        chroma_client.connect()
        chroma_available = chroma_client.is_connected
        if chroma_available:
            logger.info("[STARTUP] ChromaDB connected")
        else:
            logger.warning("[STARTUP] ChromaDB not available — RAG search disabled")
    except Exception as exc:
        logger.warning("[STARTUP] ChromaDB init failed: %s", exc)

    # --- Init Scraper Scheduler (optional — runs registered scrapers) ---
    scraper_scheduler = None
    try:
        from core.scraper.scheduler import ScraperScheduler
        scraper_scheduler = ScraperScheduler()
        logger.info("[STARTUP] Scraper scheduler initialized")
    except Exception as exc:
        logger.warning("[STARTUP] Scraper scheduler init failed: %s", exc)

    # --- Init Task Runner (optional — runs registered background tasks) ---
    task_runner = None
    try:
        from core.scheduler.runner import TaskRunner
        task_runner = TaskRunner()
        logger.info("[STARTUP] Task runner initialized")
    except Exception as exc:
        logger.warning("[STARTUP] Task runner init failed: %s", exc)

    # Create voice pipeline (with multi-provider LLM router)
    logger.info("[STARTUP] Creating voice pipeline (STT + LLM Router + TTS)...")
    pipeline = VoicePipeline(
        stt=stt_service,
        tts=tts_service,
        llm=ollama_client,
        model_manager=model_manager,
        registry=registry,
        session_store=session_store,
        llm_router=llm_router,
    )

    logger.info("")
    logger.info("=" * 60)
    logger.info("  BHARATAI PLATFORM READY — http://localhost:8000")
    logger.info("=" * 60)
    logger.info("  PostgreSQL: %s", "CONNECTED" if db_available else "OFFLINE (in-memory)")
    logger.info("  Redis:      %s", "CONNECTED" if redis_available else "OFFLINE (in-memory)")
    logger.info("  Ollama:     %s", "CONNECTED" if ollama_available else "OFFLINE")
    logger.info("  ChromaDB:   %s", "CONNECTED" if chroma_available else "OFFLINE (no RAG)")
    logger.info("  Plugins:    %s", list(registry.plugins.keys()))
    logger.info("")
    logger.info("  [LLM Providers]")
    for name, prov in llm_router.providers.items():
        locality = "LOCAL GPU" if name in ("ollama", "openai_compatible") else "CLOUD API"
        models_list = prov.list_models()
        logger.info("    ✅ %-16s — %s — models: %s", name, locality, ", ".join(models_list[:4]) or "auto")
    # Show unconfigured providers
    for name in ("ollama", "groq", "gemini", "claude", "sarvam"):
        if name not in llm_router.providers:
            logger.info("    ❌ %-16s — NO API KEY", name)
    logger.info("")
    logger.info("  [App Model Config]")
    configs = llm_router.get_all_configs()
    default_cfg = configs.get("default", {})
    for app_id in registry.plugins:
        if app_id in configs:
            cfg = configs[app_id]
            fb_str = " → ".join(f"{f['provider']}" for f in cfg.get("fallback_chain", []))
            logger.info("    %-16s → %s/%s%s", app_id, cfg["provider"], cfg["model"], f" (fallback: {fb_str})" if fb_str else "")
        else:
            if default_cfg:
                logger.info("    %-16s → default (%s/%s)", app_id, default_cfg.get("provider", "?"), default_cfg.get("model", "?"))
            else:
                logger.info("    %-16s → default", app_id)
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("[SHUTDOWN] BharatAI Platform shutting down...")
    if scraper_scheduler:
        await scraper_scheduler.stop()
    if task_runner:
        await task_runner.stop()
    await llm_router.close()
    await ollama_client.close()
    await session_store.close()
    try:
        from core.db.base import close_db
        await close_db()
    except Exception:
        pass
    logger.info("[SHUTDOWN] Cleanup complete.")


async def _register_llm_providers(ollama_available: bool) -> None:
    """Auto-register LLM providers based on available API keys."""
    from core.llm.providers.ollama_provider import OllamaProvider
    from core.llm.providers.groq_provider import GroqProvider
    from core.llm.providers.gemini_provider import GeminiProvider
    from core.llm.providers.claude_provider import ClaudeProvider
    from core.llm.providers.sarvam_provider import SarvamProvider
    from core.llm.providers.openai_compatible_provider import OpenAICompatibleProvider

    # Always register Ollama (local)
    ollama_prov = OllamaProvider()
    if ollama_available:
        await ollama_prov.refresh_models()
    llm_router.register_provider(ollama_prov)

    # Register cloud providers if API keys are set
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        llm_router.register_provider(GroqProvider(api_key=groq_key))
        logger.info("[STARTUP] Groq provider registered")

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        llm_router.register_provider(GeminiProvider(api_key=gemini_key))
        logger.info("[STARTUP] Gemini provider registered")

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        llm_router.register_provider(ClaudeProvider(api_key=anthropic_key))
        logger.info("[STARTUP] Claude provider registered")

    sarvam_key = os.getenv("SARVAM_API_KEY", "")
    if sarvam_key:
        llm_router.register_provider(SarvamProvider(api_key=sarvam_key))
        logger.info("[STARTUP] Sarvam provider registered")

    openai_base = os.getenv("OPENAI_API_BASE", "")
    if openai_base:
        llm_router.register_provider(OpenAICompatibleProvider(api_base=openai_base))
        logger.info("[STARTUP] OpenAI-compatible provider registered (%s)", openai_base)

    # Set default config from environment
    default_config = config_store.get_default_config()
    llm_router.set_default_config(default_config)

    # Load saved configs from Redis/DB into the router
    await config_store.load_all_to_router(llm_router)

    logger.info("[STARTUP] LLM Router ready: %d providers registered", len(llm_router.providers))


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

    # Register admin LLM management routes
    from core.api.admin_llm import create_admin_llm_router
    admin_llm_router = create_admin_llm_router(llm_router, config_store)
    app.include_router(admin_llm_router)

    # Register plugin routes
    _register_plugin_routes(app)

    return app


def _register_core_routes(app: FastAPI) -> None:
    """Register platform-wide routes."""

    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        """Platform health check with dependency status."""
        # Check each dependency
        db_ok = False
        try:
            from core.db.base import get_engine
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            db_ok = True
        except Exception:
            pass

        redis_ok = False
        try:
            redis = await session_store._get_redis()
            await redis.ping()
            redis_ok = True
        except Exception:
            pass

        ollama_ok = await ollama_client.is_healthy()

        chroma_ok = False
        try:
            from core.db.chroma_client import ChromaClient
            # Check module-level state if available
            chroma_ok = chroma_available
        except Exception:
            pass

        return {
            "status": "healthy",
            "platform": "BharatAI",
            "version": "1.0.0-mvp",
            "plugins_loaded": list(registry.plugins.keys()),
            "model_status": model_manager.status(),
            "dependencies": {
                "postgresql": "connected" if db_ok else "offline",
                "redis": "connected" if redis_ok else "offline",
                "ollama": "connected" if ollama_ok else "offline",
                "chromadb": "connected" if chroma_ok else "offline",
            },
        }

    @app.get("/models")
    async def list_models() -> dict[str, Any]:
        """List loaded models and VRAM usage."""
        return model_manager.status()

    @app.get("/admin/available-models")
    async def available_models() -> dict[str, Any]:
        """List all available models that can be loaded."""
        logger.info("[ROUTE] GET /admin/available-models")
        models = model_manager.list_available_models()
        return {
            "models": models,
            "active_model": model_manager.active_model_key,
            "vram_status": model_manager.status(),
        }

    @app.post("/admin/switch-model")
    async def switch_model(request: Request) -> dict[str, Any]:
        """Switch the active model. Pulls from Ollama if not available locally."""
        body = await request.json()
        model_key = body.get("model_key")
        if not model_key:
            return JSONResponse(
                status_code=400,
                content={"detail": "model_key is required"},
            )

        logger.info("[ROUTE] POST /admin/switch-model — switching to '%s'", model_key)

        try:
            status = model_manager.load(model_key)
            logger.info("[ROUTE] Model switched to '%s' (tag=%s, vram=%dMB)", model_key, status.ollama_tag, status.vram_mb)
            return {
                "message": f"Switched to '{status.ollama_tag}'",
                "model_key": status.model_key,
                "ollama_tag": status.ollama_tag,
                "vram_mb": status.vram_mb,
                "pull_command": f"ollama pull {status.ollama_tag}",
            }
        except Exception as exc:
            logger.error("[ROUTE] Model switch failed: %s", exc)
            return JSONResponse(
                status_code=400,
                content={"detail": str(exc)},
            )

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
