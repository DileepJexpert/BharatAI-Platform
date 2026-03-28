"""Speech-to-text service wrapping faster-whisper."""

import io
import logging
import os
import asyncio
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# IndicWhisper medium — optimised for Indian languages (Hindi, Tamil, Bengali, etc.)
# Set WHISPER_MODEL_SIZE=medium to use generic Whisper instead
WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "ai4bharat/indicwhisper-medium")
WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "float16")


class STTError(Exception):
    """Raised when transcription fails."""
    pass


class STTModelNotLoadedError(Exception):
    """Raised when the Whisper model is not loaded."""
    pass


@dataclass
class TranscriptResult:
    """Result of speech-to-text transcription."""
    text: str
    language: str
    confidence: float
    duration_ms: int


class STTService:
    """Wrapper around faster-whisper for speech-to-text."""

    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
    ) -> None:
        self.model_size = model_size or WHISPER_MODEL_SIZE
        self.device = device or WHISPER_DEVICE
        self.compute_type = compute_type or WHISPER_COMPUTE_TYPE
        self._model: Any = None

    @property
    def is_loaded(self) -> bool:
        """Check if the Whisper model is loaded."""
        return self._model is not None

    def _load_model(self) -> None:
        """Load the faster-whisper model. Called lazily on first transcribe."""
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info(
                "Whisper model loaded: size=%s, device=%s, compute=%s",
                self.model_size, self.device, self.compute_type,
            )
        except Exception as exc:
            raise STTError(f"Failed to load Whisper model: {exc}") from exc

    def unload(self) -> None:
        """Unload the model to free VRAM."""
        if self._model is not None:
            del self._model
            self._model = None
            logger.info("Whisper model unloaded")

    async def transcribe(
        self,
        audio: bytes,
        language_hint: str | None = None,
    ) -> TranscriptResult:
        """Transcribe audio bytes to text.

        Args:
            audio: WAV or OGG audio bytes.
            language_hint: optional ISO language code to guide transcription.

        Returns:
            TranscriptResult with text, detected language, confidence, duration.

        Raises:
            STTError: on transcription failure or corrupted audio.
        """
        if not audio or len(audio) < 100:
            return TranscriptResult(text="", language=language_hint or "hi", confidence=0.0, duration_ms=0)

        # Run in thread pool since faster-whisper is blocking
        return await asyncio.get_event_loop().run_in_executor(
            None, self._transcribe_sync, audio, language_hint
        )

    def _transcribe_sync(
        self,
        audio: bytes,
        language_hint: str | None,
    ) -> TranscriptResult:
        """Synchronous transcription (runs in executor)."""
        if not self.is_loaded:
            self._load_model()

        try:
            audio_file = io.BytesIO(audio)

            kwargs: dict[str, Any] = {}
            if language_hint:
                kwargs["language"] = language_hint

            segments, info = self._model.transcribe(audio_file, **kwargs)

            # Collect all segment texts
            texts: list[str] = []
            total_confidence: float = 0.0
            segment_count: int = 0

            for segment in segments:
                texts.append(segment.text.strip())
                total_confidence += getattr(segment, "avg_logprob", -0.5)
                segment_count += 1

            full_text = " ".join(texts).strip()

            # Convert avg_logprob to a 0-1 confidence score
            # logprob of 0 = perfect, -1 = poor
            if segment_count > 0:
                avg_logprob = total_confidence / segment_count
                confidence = max(0.0, min(1.0, 1.0 + avg_logprob))
            else:
                confidence = 0.0

            duration_ms = int(info.duration * 1000) if info.duration else 0

            return TranscriptResult(
                text=full_text,
                language=info.language or language_hint or "hi",
                confidence=round(confidence, 2),
                duration_ms=duration_ms,
            )

        except Exception as exc:
            raise STTError(f"Transcription failed: {exc}") from exc
