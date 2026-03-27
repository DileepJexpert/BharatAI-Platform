"""Pydantic models for voice pipeline request/response."""

from pydantic import BaseModel, Field
from typing import Any


class VoiceResponse(BaseModel):
    """Response from the voice pipeline."""
    session_id: str | None = None
    transcript: str | None = None
    language: str | None = None
    response_text: str | None = None
    response_audio: bytes | None = Field(default=None, exclude=True)
    response_audio_url: str | None = None
    domain_data: dict[str, Any] | None = None
    confidence: float | None = None
    processing_ms: int | None = None
    error: str | None = None


class ChatRequest(BaseModel):
    """Text-only chat request."""
    text: str
    session_id: str
    language_hint: str | None = None


class ChatResponse(BaseModel):
    """Text-only chat response."""
    session_id: str
    response_text: str | None = None
    domain_data: dict[str, Any] | None = None
    language: str | None = None
    error: str | None = None
