"""Voice pipeline — STT → LLM → TTS chain with error handling."""

import json
import logging
import time
from typing import Any

from core.api.plugin_registry import BasePlugin, PluginRegistry
from core.language.detector import detect as detect_language
from core.llm.client import OllamaClient
from core.llm.model_manager import ModelManager, ModelNotLoadedError
from core.llm.prompt_builder import build_messages, build_system_prompt
from core.llm.router import LLMRouter
from core.voice.models import VoiceResponse
from core.voice.session_store import SessionStore
from core.voice.stt import STTService
from core.voice.tts import TTSService

logger = logging.getLogger("pipeline")


class PipelineError(Exception):
    """Raised for unrecoverable pipeline errors."""
    pass


class VoicePipeline:
    """Orchestrates STT → LLM → TTS for voice requests.

    Handles:
    - Low-confidence STT (< threshold): returns "please repeat"
    - Invalid JSON from LLM: retries once, then returns error
    - TTS failure: returns text-only response (audio=None)
    """

    MIN_STT_CONFIDENCE: float = 0.5
    LLM_RETRY_LIMIT: int = 1
    MAX_AUDIO_SIZE: int = 10 * 1024 * 1024  # 10MB

    def __init__(
        self,
        stt: STTService,
        tts: TTSService,
        llm: OllamaClient,
        model_manager: ModelManager,
        registry: PluginRegistry,
        session_store: SessionStore,
        llm_router: LLMRouter | None = None,
    ) -> None:
        self.stt = stt
        self.tts = tts
        self.llm = llm
        self.model_manager = model_manager
        self.registry = registry
        self.session_store = session_store
        self.llm_router = llm_router

    async def process(
        self,
        audio: bytes,
        app_id: str,
        session_id: str,
        language_hint: str | None = None,
    ) -> VoiceResponse:
        """Process a voice request through the full pipeline.

        Args:
            audio: raw audio bytes (WAV or OGG).
            app_id: plugin slug.
            session_id: session UUID.
            language_hint: optional ISO language code.

        Returns:
            VoiceResponse with transcript, response text, audio, and domain data.
        """
        start_time = time.monotonic()

        # Validate audio size
        if len(audio) > self.MAX_AUDIO_SIZE:
            return VoiceResponse(
                session_id=session_id,
                error="audio_too_large",
                response_text="Audio file is too large. Maximum size is 10MB.",
            )

        # Validate plugin exists
        plugin = self.registry.get(app_id)
        if plugin is None:
            return VoiceResponse(
                session_id=session_id,
                error="unknown_app",
                response_text=f"Unknown application: {app_id}",
            )

        # Step 1 — Transcribe
        try:
            transcript = await self.stt.transcribe(audio, language_hint)
        except Exception as exc:
            logger.error("STT failed: %s", exc)
            return VoiceResponse(
                session_id=session_id,
                error="stt_failed",
                response_text="Could not process the audio. Please try again.",
            )

        # Step 1b — Reject low confidence
        if transcript.confidence < self.MIN_STT_CONFIDENCE:
            low_conf_text = "Sorry, I could not understand. Please speak again."
            audio_out = await self._safe_tts(low_conf_text, language_hint or "hi")
            return VoiceResponse(
                session_id=session_id,
                transcript=transcript.text,
                confidence=transcript.confidence,
                error="low_confidence",
                response_text=low_conf_text,
                response_audio=audio_out,
                processing_ms=self._elapsed_ms(start_time),
            )

        # Step 2 — Detect language
        if language_hint:
            language = language_hint
        else:
            lang_result = await detect_language(transcript.text)
            language = lang_result.language_code

        # Step 3 — Get/create session, build prompt
        session = await self.session_store.get(session_id)
        if session is None:
            session = await self.session_store.create(
                session_id=session_id,
                app_id=app_id,
                language=language,
            )

        system_prompt = plugin.system_prompt(language, session)

        # Step 4 — LLM inference with retry (routes to correct provider via LLMRouter)
        parsed = await self._llm_with_retry(
            plugin, system_prompt, transcript.text, session, start_time, session_id,
            app_id=app_id,
        )
        if isinstance(parsed, VoiceResponse):
            # _llm_with_retry returned an error response
            return parsed

        # Step 5 — Update session
        await self.session_store.add_turn(session_id, "user", transcript.text)
        response_text = parsed.get("response_text") or parsed.get("confirmation_message", "")
        await self.session_store.add_turn(session_id, "assistant", response_text)

        # Step 6 — TTS with fallback
        audio_out = await self._safe_tts(response_text, language)

        return VoiceResponse(
            session_id=session_id,
            transcript=transcript.text,
            language=language,
            response_text=response_text,
            response_audio=audio_out,
            domain_data=parsed,
            confidence=transcript.confidence,
            processing_ms=self._elapsed_ms(start_time),
            error=None,
        )

    async def process_text(
        self,
        text: str,
        app_id: str,
        session_id: str,
        language_hint: str | None = None,
    ) -> VoiceResponse:
        """Process a text-only request (no STT/TTS, just LLM).

        Args:
            text: user text input.
            app_id: plugin slug.
            session_id: session UUID.
            language_hint: optional ISO language code.

        Returns:
            VoiceResponse (without audio).
        """
        start_time = time.monotonic()
        logger.info("[CHAT] === New text request: app=%s session=%s ===", app_id, session_id)
        logger.info("[CHAT] User text: %s", text[:200])

        plugin = self.registry.get(app_id)
        if plugin is None:
            logger.error("[CHAT] Unknown app: %s", app_id)
            return VoiceResponse(
                session_id=session_id,
                error="unknown_app",
                response_text=f"Unknown application: {app_id}",
            )

        # Detect language
        logger.info("[CHAT] Step 1: Detecting language...")
        if language_hint:
            language = language_hint
        else:
            lang_result = await detect_language(text)
            language = lang_result.language_code
        logger.info("[CHAT] Language detected: %s (%dms)", language, self._elapsed_ms(start_time))

        # Get/create session
        logger.info("[CHAT] Step 2: Getting/creating session...")
        session = await self.session_store.get(session_id)
        if session is None:
            session = await self.session_store.create(
                session_id=session_id,
                app_id=app_id,
                language=language,
            )
            logger.info("[CHAT] New session created (%dms)", self._elapsed_ms(start_time))
        else:
            logger.info("[CHAT] Existing session loaded (%dms)", self._elapsed_ms(start_time))

        system_prompt = plugin.system_prompt(language, session)
        logger.info("[CHAT] Step 3: Calling LLM (this may take a while)...")

        # LLM with retry (routes to correct provider via LLMRouter)
        parsed = await self._llm_with_retry(
            plugin, system_prompt, text, session, start_time, session_id,
            app_id=app_id,
        )
        if isinstance(parsed, VoiceResponse):
            logger.error("[CHAT] LLM failed after %dms: %s", self._elapsed_ms(start_time), parsed.error)
            return parsed

        logger.info("[CHAT] LLM responded in %dms", self._elapsed_ms(start_time))

        # Update session
        await self.session_store.add_turn(session_id, "user", text)
        response_text = parsed.get("response_text") or parsed.get("confirmation_message", "")
        await self.session_store.add_turn(session_id, "assistant", response_text)
        logger.info("[CHAT] Response: %s", response_text[:200])
        logger.info("[CHAT] === Done in %dms ===", self._elapsed_ms(start_time))

        return VoiceResponse(
            session_id=session_id,
            transcript=text,
            language=language,
            response_text=response_text,
            domain_data=parsed,
            processing_ms=self._elapsed_ms(start_time),
            error=None,
        )

    async def _llm_with_retry(
        self,
        plugin: BasePlugin,
        system_prompt: str,
        user_text: str,
        session: dict,
        start_time: float,
        session_id: str,
        app_id: str | None = None,
    ) -> dict | VoiceResponse:
        """Call LLM and parse response, retrying once on JSON errors.

        Uses LLMRouter if available (multi-provider), otherwise falls back
        to direct OllamaClient.

        Returns parsed dict on success, or VoiceResponse on failure.
        """
        # Determine if we can use the router
        use_router = self.llm_router is not None and app_id is not None

        if not use_router:
            try:
                active_model = self.model_manager.active_model
            except ModelNotLoadedError:
                return VoiceResponse(
                    session_id=session_id,
                    error="model_not_loaded",
                    response_text="The AI model is not ready yet. Please try again shortly.",
                    processing_ms=self._elapsed_ms(start_time),
                )

        history = session.get("conversation_history", [])
        messages = build_messages(system_prompt, user_text, history)

        for attempt in range(self.LLM_RETRY_LIMIT + 1):
            try:
                if use_router:
                    router_response = await self.llm_router.chat(app_id, messages)
                    llm_text = router_response.text
                    logger.info(
                        "LLM via router: provider=%s model=%s latency=%dms fallback=%s",
                        router_response.provider, router_response.model,
                        router_response.latency_ms, router_response.fallback,
                    )
                else:
                    llm_response = await self.llm.chat(
                        system=system_prompt,
                        user=user_text,
                        model=active_model,
                    )
                    llm_text = llm_response.text

                parsed = plugin.parse_response(llm_text, session)
                return parsed

            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.warning(
                    "LLM parse attempt %d failed: %s", attempt + 1, exc
                )
                if attempt >= self.LLM_RETRY_LIMIT:
                    return VoiceResponse(
                        session_id=session_id,
                        transcript=user_text,
                        error="parse_failed",
                        response_text="I understood you but could not process the response. Please try again.",
                        processing_ms=self._elapsed_ms(start_time),
                    )

            except Exception as exc:
                logger.error("LLM call failed: %s", exc)
                return VoiceResponse(
                    session_id=session_id,
                    transcript=user_text,
                    error="llm_error",
                    response_text="AI service is temporarily unavailable. Please try again.",
                    processing_ms=self._elapsed_ms(start_time),
                )

        # Should not reach here, but just in case
        return VoiceResponse(
            session_id=session_id,
            error="unknown_error",
            response_text="An unexpected error occurred.",
            processing_ms=self._elapsed_ms(start_time),
        )

    async def _safe_tts(self, text: str, language: str) -> bytes | None:
        """TTS with graceful fallback — returns None on failure."""
        try:
            return await self.tts.synthesize(text=text, language=language)
        except Exception as exc:
            logger.warning("TTS failed (returning text-only): %s", exc)
            return None

    def _elapsed_ms(self, start_time: float) -> int:
        """Calculate elapsed milliseconds since start_time."""
        return int((time.monotonic() - start_time) * 1000)
