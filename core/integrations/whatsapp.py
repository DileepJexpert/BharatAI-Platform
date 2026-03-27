"""Twilio WhatsApp webhook handler.

Receives WhatsApp messages (voice or text) via Twilio webhook,
forwards them through the BharatAI voice/chat pipeline,
and returns TwiML responses.
"""

import logging
import os
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import Response

logger = logging.getLogger(__name__)

# Map Twilio phone numbers to app_ids
# Configure via env: WHATSAPP_NUMBER_ASHA_HEALTH=whatsapp:+14155238886
PHONE_TO_APP: dict[str, str] = {}

# Default app_id if phone number mapping not found
DEFAULT_APP_ID: str = os.getenv("WHATSAPP_DEFAULT_APP_ID", "asha_health")

router = APIRouter(tags=["whatsapp"])


def _load_phone_mappings() -> None:
    """Load phone number → app_id mappings from environment."""
    global PHONE_TO_APP
    for key, value in os.environ.items():
        if key.startswith("WHATSAPP_NUMBER_"):
            # WHATSAPP_NUMBER_ASHA_HEALTH=whatsapp:+14155238886
            app_id = key[len("WHATSAPP_NUMBER_"):].lower()
            PHONE_TO_APP[value] = app_id


def _build_twiml_response(message: str, media_url: str | None = None) -> str:
    """Build a TwiML XML response for WhatsApp.

    Args:
        message: text message to send back.
        media_url: optional URL to an audio file.

    Returns:
        TwiML XML string.
    """
    media_tag = f"\n        <Media>{media_url}</Media>" if media_url else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>
        <Body>{message}</Body>{media_tag}
    </Message>
</Response>"""


def _get_session_id(from_number: str, app_id: str) -> str:
    """Generate a deterministic session ID from the sender's phone + app.

    This means the same WhatsApp user always continues their session.
    """
    import hashlib
    raw = f"{from_number}:{app_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    From: str = Form(default=""),
    To: str = Form(default=""),
    Body: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: str = Form(default=""),
    MediaContentType0: str = Form(default=""),
) -> Response:
    """Handle incoming Twilio WhatsApp webhook.

    Supports:
    - Voice messages: downloads audio, forwards to /{app_id}/voice pipeline
    - Text messages: forwards to /{app_id}/chat pipeline

    Returns TwiML response with text (and audio URL if available).
    """
    # Lazy load phone mappings
    if not PHONE_TO_APP:
        _load_phone_mappings()

    # Determine app_id from the Twilio number receiving the message
    app_id = PHONE_TO_APP.get(To, DEFAULT_APP_ID)
    session_id = _get_session_id(From, app_id)

    logger.info(
        "WhatsApp message from=%s to=%s app=%s media=%s",
        From, To, app_id, NumMedia,
    )

    # Import pipeline lazily to avoid circular imports
    from core.api.gateway import pipeline

    if pipeline is None:
        return Response(
            content=_build_twiml_response("Service is starting up. Please try again in a moment."),
            media_type="application/xml",
        )

    has_audio = int(NumMedia) > 0 and "audio" in MediaContentType0.lower()

    if has_audio:
        # Download audio from Twilio
        try:
            audio_bytes = await _download_media(MediaUrl0)
        except Exception as exc:
            logger.error("Failed to download WhatsApp audio: %s", exc)
            return Response(
                content=_build_twiml_response("Could not process your voice message. Please try again."),
                media_type="application/xml",
            )

        # Process through voice pipeline
        result = await pipeline.process(
            audio=audio_bytes,
            app_id=app_id,
            session_id=session_id,
        )
    elif Body.strip():
        # Text message — process through text pipeline
        result = await pipeline.process_text(
            text=Body.strip(),
            app_id=app_id,
            session_id=session_id,
        )
    else:
        return Response(
            content=_build_twiml_response("Please send a voice message or text."),
            media_type="application/xml",
        )

    # Build response
    response_text = result.response_text or "I could not understand. Please try again."

    # TODO: store audio and provide URL for audio responses
    return Response(
        content=_build_twiml_response(response_text),
        media_type="application/xml",
    )


async def _download_media(url: str) -> bytes:
    """Download media from a Twilio media URL.

    Args:
        url: Twilio media URL.

    Returns:
        Audio bytes.

    Raises:
        httpx.HTTPError: if download fails.
    """
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")

    async with httpx.AsyncClient() as client:
        if twilio_sid and twilio_token:
            response = await client.get(url, auth=(twilio_sid, twilio_token), timeout=30.0)
        else:
            response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        return response.content
