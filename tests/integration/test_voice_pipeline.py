"""Integration tests for VoicePipeline — VP-001 through VP-008.

All external services (STT, LLM, TTS) are mocked at the service boundary.
Tests the pipeline orchestration logic.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
from fastapi import APIRouter

from core.api.plugin_registry import BasePlugin, PluginRegistry
from core.llm.client import OllamaClient, LLMResponse, OllamaTimeoutError
from core.llm.model_manager import ModelManager
from core.voice.models import VoiceResponse
from core.voice.pipeline import VoicePipeline
from core.voice.session_store import SessionStore
from core.voice.stt import STTService, TranscriptResult
from core.voice.tts import TTSService, TTSError


# --- Mock Plugin ---

class MockAshaPlugin(BasePlugin):
    """Mock ASHA Health plugin for pipeline testing."""

    @property
    def app_id(self) -> str:
        return "asha_health"

    def system_prompt(self, language: str, context: dict) -> str:
        return f"You are a health assistant. Respond in JSON. Language: {language}"

    def parse_response(self, llm_output: str, context: dict) -> dict:
        # Strip markdown fences if present
        cleaned = llm_output.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        data = json.loads(cleaned)
        if "response_text" not in data and "confirmation_message" in data:
            data["response_text"] = data["confirmation_message"]
        return data

    def router(self) -> APIRouter:
        return APIRouter()


VALID_ASHA_JSON = json.dumps({
    "patient_name": "राम",
    "patient_age": 45,
    "gender": "male",
    "complaint": "बुखार",
    "temperature": None,
    "weight": None,
    "visit_date": "2026-03-27",
    "referral_needed": False,
    "notes": None,
    "confirmation_message": "राम, 45 साल, बुखार का दौरा दर्ज किया गया।",
    "response_text": "राम, 45 साल, बुखार का दौरा दर्ज किया गया।",
})

VALID_MARATHI_JSON = json.dumps({
    "patient_name": "सुरेश",
    "patient_age": 30,
    "gender": "male",
    "complaint": "ताप",
    "temperature": None,
    "weight": None,
    "visit_date": "2026-03-27",
    "referral_needed": False,
    "notes": None,
    "confirmation_message": "सुरेश, 30 वर्षे, ताप नोंदवला.",
    "response_text": "सुरेश, 30 वर्षे, ताप नोंदवला.",
})


# --- Fixtures ---

@pytest.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def session_store(redis_client):
    return SessionStore(redis_client=redis_client)


@pytest.fixture
def registry():
    reg = PluginRegistry()
    reg.register(MockAshaPlugin())
    return reg


@pytest.fixture
def model_manager():
    mm = ModelManager()
    mm.load("llama3.2:3b")
    return mm


@pytest.fixture
def mock_stt():
    stt = STTService(device="cpu")
    stt.transcribe = AsyncMock()
    return stt


@pytest.fixture
def mock_tts():
    tts = TTSService()
    tts.synthesize = AsyncMock(return_value=b"fake-audio-bytes")
    return tts


@pytest.fixture
def mock_llm():
    client = OllamaClient()
    client.chat = AsyncMock()
    return client


@pytest.fixture
async def pipeline(mock_stt, mock_tts, mock_llm, model_manager, registry, session_store):
    return VoicePipeline(
        stt=mock_stt,
        tts=mock_tts,
        llm=mock_llm,
        model_manager=model_manager,
        registry=registry,
        session_store=session_store,
    )


# --- Tests ---

class TestVP001FullPipelineHindi:
    """VP-001: Full pipeline Hindi — JSON + audio response in Hindi."""

    @pytest.mark.asyncio
    async def test_hindi_pipeline(self, pipeline, mock_stt, mock_llm):
        mock_stt.transcribe.return_value = TranscriptResult(
            text="राम 45 साल बुखार है",
            language="hi",
            confidence=0.92,
            duration_ms=3000,
        )
        mock_llm.chat.return_value = LLMResponse(
            text=VALID_ASHA_JSON,
            model="llama3.2:3b",
            total_duration_ms=1500,
            prompt_eval_count=50,
            eval_count=30,
        )

        result = await pipeline.process(
            audio=b"\x00" * 5000,
            app_id="asha_health",
            session_id="sess-001",
            language_hint="hi",
        )

        assert result.error is None
        assert result.transcript == "राम 45 साल बुखार है"
        assert result.language == "hi"
        assert result.domain_data is not None
        assert result.domain_data["patient_name"] == "राम"
        assert result.domain_data["patient_age"] == 45
        assert result.response_text is not None
        assert result.response_audio == b"fake-audio-bytes"
        assert result.confidence == 0.92


class TestVP002FullPipelineMarathi:
    """VP-002: Full pipeline Marathi — JSON + audio response in Marathi."""

    @pytest.mark.asyncio
    async def test_marathi_pipeline(self, pipeline, mock_stt, mock_llm):
        mock_stt.transcribe.return_value = TranscriptResult(
            text="सुरेश 30 वर्षे ताप आहे",
            language="mr",
            confidence=0.88,
            duration_ms=2500,
        )
        mock_llm.chat.return_value = LLMResponse(
            text=VALID_MARATHI_JSON,
            model="llama3.2:3b",
            total_duration_ms=1400,
            prompt_eval_count=45,
            eval_count=25,
        )

        result = await pipeline.process(
            audio=b"\x00" * 5000,
            app_id="asha_health",
            session_id="sess-002",
        )

        assert result.error is None
        assert result.domain_data["patient_name"] == "सुरेश"
        assert result.domain_data["complaint"] == "ताप"


class TestVP003SessionContinuity:
    """VP-003: Session continuity — second request has access to first's context."""

    @pytest.mark.asyncio
    async def test_session_persists(self, pipeline, mock_stt, mock_llm, session_store):
        mock_stt.transcribe.return_value = TranscriptResult(
            text="राम 45 साल बुखार है",
            language="hi",
            confidence=0.92,
            duration_ms=3000,
        )
        mock_llm.chat.return_value = LLMResponse(
            text=VALID_ASHA_JSON,
            model="llama3.2:3b",
            total_duration_ms=1500,
            prompt_eval_count=50,
            eval_count=30,
        )

        session_id = "sess-continuity"

        # First request
        await pipeline.process(
            audio=b"\x00" * 5000,
            app_id="asha_health",
            session_id=session_id,
            language_hint="hi",
        )

        # Check session was created with conversation history
        session = await session_store.get(session_id)
        assert session is not None
        assert len(session["conversation_history"]) == 2  # user + assistant
        assert session["conversation_history"][0]["role"] == "user"
        assert session["conversation_history"][1]["role"] == "assistant"

        # Second request on same session
        mock_stt.transcribe.return_value = TranscriptResult(
            text="temperature bhi check karo",
            language="hi",
            confidence=0.85,
            duration_ms=2000,
        )

        await pipeline.process(
            audio=b"\x00" * 5000,
            app_id="asha_health",
            session_id=session_id,
            language_hint="hi",
        )

        session = await session_store.get(session_id)
        assert len(session["conversation_history"]) == 4  # 2 turns


class TestVP004InvalidAppId:
    """VP-004: Invalid app_id — returns error with 'unknown_app'."""

    @pytest.mark.asyncio
    async def test_invalid_app_id(self, pipeline):
        result = await pipeline.process(
            audio=b"\x00" * 5000,
            app_id="nonexistent",
            session_id="sess-004",
        )

        assert result.error == "unknown_app"
        assert "nonexistent" in result.response_text


class TestVP005OversizedAudio:
    """VP-005: Oversized audio — WAV > 10MB returns error."""

    @pytest.mark.asyncio
    async def test_oversized_audio(self, pipeline):
        huge_audio = b"\x00" * (11 * 1024 * 1024)  # 11MB

        result = await pipeline.process(
            audio=huge_audio,
            app_id="asha_health",
            session_id="sess-005",
        )

        assert result.error == "audio_too_large"
        assert "10MB" in result.response_text


class TestVP006LowConfidenceSTT:
    """VP-006: Low confidence STT — returns 'please repeat', no LLM call."""

    @pytest.mark.asyncio
    async def test_low_confidence(self, pipeline, mock_stt, mock_llm):
        mock_stt.transcribe.return_value = TranscriptResult(
            text="...",
            language="hi",
            confidence=0.2,
            duration_ms=2000,
        )

        result = await pipeline.process(
            audio=b"\x00" * 5000,
            app_id="asha_health",
            session_id="sess-006",
        )

        assert result.error == "low_confidence"
        assert "speak again" in result.response_text.lower()
        # LLM should NOT have been called
        mock_llm.chat.assert_not_called()


class TestVP007BadLLMJSON:
    """VP-007: Bad LLM JSON — retry once, then return error."""

    @pytest.mark.asyncio
    async def test_bad_json_retry(self, pipeline, mock_stt, mock_llm):
        mock_stt.transcribe.return_value = TranscriptResult(
            text="राम 45 साल बुखार है",
            language="hi",
            confidence=0.92,
            duration_ms=3000,
        )

        # First call returns invalid JSON, second returns valid
        mock_llm.chat.side_effect = [
            LLMResponse(
                text="Sure! Here is the data: not json",
                model="llama3.2:3b",
                total_duration_ms=1500,
                prompt_eval_count=50,
                eval_count=30,
            ),
            LLMResponse(
                text=VALID_ASHA_JSON,
                model="llama3.2:3b",
                total_duration_ms=1500,
                prompt_eval_count=50,
                eval_count=30,
            ),
        ]

        result = await pipeline.process(
            audio=b"\x00" * 5000,
            app_id="asha_health",
            session_id="sess-007",
            language_hint="hi",
        )

        # Should have retried and succeeded
        assert result.error is None
        assert result.domain_data["patient_name"] == "राम"
        assert mock_llm.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_bad_json_both_attempts_fail(self, pipeline, mock_stt, mock_llm):
        mock_stt.transcribe.return_value = TranscriptResult(
            text="राम 45 साल बुखार है",
            language="hi",
            confidence=0.92,
            duration_ms=3000,
        )

        # Both calls return invalid JSON
        mock_llm.chat.return_value = LLMResponse(
            text="I cannot parse this properly",
            model="llama3.2:3b",
            total_duration_ms=1500,
            prompt_eval_count=50,
            eval_count=30,
        )

        result = await pipeline.process(
            audio=b"\x00" * 5000,
            app_id="asha_health",
            session_id="sess-007b",
            language_hint="hi",
        )

        assert result.error == "parse_failed"
        assert "could not process" in result.response_text.lower()


class TestVP008TTSFailure:
    """VP-008: TTS failure — text response returned, audio=None."""

    @pytest.mark.asyncio
    async def test_tts_failure_returns_text(self, pipeline, mock_stt, mock_llm, mock_tts):
        mock_stt.transcribe.return_value = TranscriptResult(
            text="राम 45 साल बुखार है",
            language="hi",
            confidence=0.92,
            duration_ms=3000,
        )
        mock_llm.chat.return_value = LLMResponse(
            text=VALID_ASHA_JSON,
            model="llama3.2:3b",
            total_duration_ms=1500,
            prompt_eval_count=50,
            eval_count=30,
        )
        # TTS throws
        mock_tts.synthesize.side_effect = TTSError("gTTS service unavailable")

        result = await pipeline.process(
            audio=b"\x00" * 5000,
            app_id="asha_health",
            session_id="sess-008",
            language_hint="hi",
        )

        assert result.error is None  # Pipeline succeeded
        assert result.response_text is not None
        assert result.response_audio is None  # TTS failed gracefully
        assert result.domain_data["patient_name"] == "राम"


class TestVPTextChat:
    """Additional: test process_text (chat endpoint)."""

    @pytest.mark.asyncio
    async def test_text_chat(self, pipeline, mock_llm):
        mock_llm.chat.return_value = LLMResponse(
            text=VALID_ASHA_JSON,
            model="llama3.2:3b",
            total_duration_ms=1000,
            prompt_eval_count=40,
            eval_count=20,
        )

        result = await pipeline.process_text(
            text="राम 45 साल बुखार है",
            app_id="asha_health",
            session_id="sess-chat",
            language_hint="hi",
        )

        assert result.error is None
        assert result.domain_data["patient_name"] == "राम"
        assert result.response_audio is None  # No TTS for text chat
