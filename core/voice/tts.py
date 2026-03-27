"""Text-to-speech service wrapping gTTS."""

import asyncio
import io
import logging

logger = logging.getLogger(__name__)

# gTTS language code mapping (ISO 639-1 -> gTTS lang)
GTTS_LANG_MAP: dict[str, str] = {
    "hi": "hi",
    "mr": "mr",
    "ta": "ta",
    "te": "te",
    "kn": "kn",
    "ml": "ml",
    "bn": "bn",
    "gu": "gu",
    "pa": "pa",
    "en": "en",
}


class TTSError(Exception):
    """Raised when TTS synthesis fails."""
    pass


class TTSService:
    """Text-to-speech using gTTS (Google Text-to-Speech).

    gTTS is CPU-only (no VRAM) and runs as blocking I/O,
    so we run it in a thread executor.
    """

    def _get_gtts_lang(self, language: str) -> str:
        """Map ISO language code to gTTS language code."""
        return GTTS_LANG_MAP.get(language, "hi")

    async def synthesize(self, text: str, language: str) -> bytes:
        """Synthesize text to audio bytes (MP3).

        Args:
            text: text to speak.
            language: ISO 639-1 language code.

        Returns:
            MP3 audio bytes.

        Raises:
            TTSError: if synthesis fails.
        """
        if not text or not text.strip():
            raise TTSError("Cannot synthesize empty text")

        return await asyncio.get_event_loop().run_in_executor(
            None, self._synthesize_sync, text, language
        )

    def _synthesize_sync(self, text: str, language: str) -> bytes:
        """Synchronous TTS (runs in thread executor)."""
        try:
            from gtts import gTTS

            gtts_lang = self._get_gtts_lang(language)
            tts = gTTS(text=text, lang=gtts_lang)

            buffer = io.BytesIO()
            tts.write_to_fp(buffer)
            buffer.seek(0)

            audio_bytes = buffer.read()
            logger.info(
                "TTS synthesized: %d chars, lang=%s, %d bytes",
                len(text), gtts_lang, len(audio_bytes),
            )
            return audio_bytes

        except Exception as exc:
            raise TTSError(f"TTS synthesis failed: {exc}") from exc
