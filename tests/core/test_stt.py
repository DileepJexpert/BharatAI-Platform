"""Tests for core/voice/stt.py — STT-001 through STT-005.

All tests mock faster-whisper so they run without a GPU.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass

from core.voice.stt import STTService, TranscriptResult, STTError


# --- Mock helpers ---

@dataclass
class MockSegment:
    text: str
    avg_logprob: float = -0.2


@dataclass
class MockInfo:
    language: str = "hi"
    duration: float = 2.5


def _make_mock_model(segments, info=None):
    """Create a mock WhisperModel that returns given segments and info."""
    model = MagicMock()
    model.transcribe.return_value = (iter(segments), info or MockInfo())
    return model


# --- Fixtures ---

@pytest.fixture
def stt_service():
    """STT service with mocked model loading."""
    service = STTService(model_size="medium", device="cpu", compute_type="int8")
    return service


def _patch_model(service, segments, info=None):
    """Inject a mock model into the service."""
    service._model = _make_mock_model(segments, info)


# --- Tests ---

class TestSTT001HindiTranscription:
    """STT-001: Hindi audio transcription — text matches, lang='hi', confidence > 0.85."""

    def test_hindi_transcription(self, stt_service):
        segments = [MockSegment(text="मरीज़ का नाम राम है", avg_logprob=-0.1)]
        info = MockInfo(language="hi", duration=3.0)
        _patch_model(stt_service, segments, info)

        result = stt_service._transcribe_sync(b"\x00" * 1000, None)

        assert result.text == "मरीज़ का नाम राम है"
        assert result.language == "hi"
        assert result.confidence > 0.85
        assert result.duration_ms == 3000


class TestSTT002BhojpuriAudio:
    """STT-002: Bhojpuri audio — transcribed (likely as Hindi), no crash."""

    def test_bhojpuri_transcription(self, stt_service):
        segments = [MockSegment(text="हमार नाम राम बा", avg_logprob=-0.3)]
        info = MockInfo(language="hi", duration=2.0)
        _patch_model(stt_service, segments, info)

        result = stt_service._transcribe_sync(b"\x00" * 1000, None)

        assert result.text == "हमार नाम राम बा"
        assert result.language == "hi"
        assert isinstance(result.confidence, float)


class TestSTT003EmptyAudio:
    """STT-003: Empty/silent audio — empty transcript, no exception."""

    @pytest.mark.asyncio
    async def test_empty_audio_bytes(self, stt_service):
        result = await stt_service.transcribe(b"", None)

        assert result.text == ""
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_tiny_audio_bytes(self, stt_service):
        result = await stt_service.transcribe(b"\x00" * 50, None)

        assert result.text == ""
        assert result.confidence == 0.0

    def test_silent_wav_returns_empty(self, stt_service):
        segments = []  # No segments from silent audio
        info = MockInfo(language="hi", duration=0.5)
        _patch_model(stt_service, segments, info)

        result = stt_service._transcribe_sync(b"\x00" * 1000, None)

        assert result.text == ""
        assert result.confidence == 0.0


class TestSTT004NoisyBackground:
    """STT-004: Noisy background — transcription attempted, confidence < 0.5."""

    def test_noisy_audio_low_confidence(self, stt_service):
        segments = [MockSegment(text="...noise...", avg_logprob=-0.8)]
        info = MockInfo(language="hi", duration=2.0)
        _patch_model(stt_service, segments, info)

        result = stt_service._transcribe_sync(b"\x00" * 1000, None)

        assert result.confidence < 0.5


class TestSTT005UnsupportedLanguage:
    """STT-005: Unsupported language (French) — transcribed, lang detected."""

    def test_french_audio(self, stt_service):
        segments = [MockSegment(text="Bonjour le monde", avg_logprob=-0.3)]
        info = MockInfo(language="fr", duration=2.0)
        _patch_model(stt_service, segments, info)

        result = stt_service._transcribe_sync(b"\x00" * 1000, None)

        assert result.text == "Bonjour le monde"
        assert result.language == "fr"


class TestSTTErrorHandling:
    """Additional: corrupted audio raises STTError."""

    def test_model_exception_raises_stt_error(self, stt_service):
        model = MagicMock()
        model.transcribe.side_effect = RuntimeError("corrupted audio")
        stt_service._model = model

        with pytest.raises(STTError, match="Transcription failed"):
            stt_service._transcribe_sync(b"\x00" * 1000, None)
