"""Tests for WhatsApp webhook handler.

Simulates Twilio webhook POST requests and verifies TwiML responses.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.integrations.whatsapp import router, _build_twiml_response, _get_session_id
from core.voice.models import VoiceResponse


@pytest.fixture
def whatsapp_app():
    """FastAPI app with WhatsApp webhook route."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestTwiMLBuilder:
    """Test TwiML response generation."""

    def test_text_only_response(self):
        xml = _build_twiml_response("Hello from BharatAI")
        assert "<Body>Hello from BharatAI</Body>" in xml
        assert "<Media>" not in xml
        assert '<?xml version="1.0"' in xml

    def test_response_with_media(self):
        xml = _build_twiml_response("Listen to this", media_url="https://example.com/audio.ogg")
        assert "<Body>Listen to this</Body>" in xml
        assert "<Media>https://example.com/audio.ogg</Media>" in xml


class TestSessionIdGeneration:
    """Test deterministic session IDs."""

    def test_same_input_same_session(self):
        s1 = _get_session_id("whatsapp:+919876543210", "asha_health")
        s2 = _get_session_id("whatsapp:+919876543210", "asha_health")
        assert s1 == s2

    def test_different_users_different_sessions(self):
        s1 = _get_session_id("whatsapp:+919876543210", "asha_health")
        s2 = _get_session_id("whatsapp:+919876543211", "asha_health")
        assert s1 != s2

    def test_different_apps_different_sessions(self):
        s1 = _get_session_id("whatsapp:+919876543210", "asha_health")
        s2 = _get_session_id("whatsapp:+919876543210", "lawyer_ai")
        assert s1 != s2


class TestWhatsAppWebhookText:
    """Test text message handling."""

    def test_text_message(self, whatsapp_app):
        mock_result = VoiceResponse(
            session_id="test-sess",
            response_text="राम, 45 साल, बुखार दर्ज किया।",
            error=None,
        )

        mock_pipeline = MagicMock()
        mock_pipeline.process_text = AsyncMock(return_value=mock_result)

        with patch("core.api.gateway.pipeline", mock_pipeline):
            response = whatsapp_app.post("/webhook/whatsapp", data={
                "From": "whatsapp:+919876543210",
                "To": "whatsapp:+14155238886",
                "Body": "राम 45 साल बुखार है",
                "NumMedia": "0",
            })

        assert response.status_code == 200
        assert "राम" in response.text
        assert "application/xml" in response.headers["content-type"]

    def test_empty_message(self, whatsapp_app):
        mock_pipeline = MagicMock()

        with patch("core.api.gateway.pipeline", mock_pipeline):
            response = whatsapp_app.post("/webhook/whatsapp", data={
                "From": "whatsapp:+919876543210",
                "To": "whatsapp:+14155238886",
                "Body": "",
                "NumMedia": "0",
            })

        assert response.status_code == 200
        assert "voice message or text" in response.text


class TestWhatsAppWebhookVoice:
    """Test voice message handling."""

    def test_voice_message(self, whatsapp_app):
        mock_result = VoiceResponse(
            session_id="test-sess",
            transcript="राम 45 साल बुखार है",
            response_text="राम का दौरा दर्ज किया।",
            error=None,
        )

        mock_pipeline = MagicMock()
        mock_pipeline.process = AsyncMock(return_value=mock_result)

        with patch("core.api.gateway.pipeline", mock_pipeline), \
             patch("core.integrations.whatsapp._download_media", new_callable=AsyncMock) as mock_dl:
            mock_dl.return_value = b"fake-audio-bytes"

            response = whatsapp_app.post("/webhook/whatsapp", data={
                "From": "whatsapp:+919876543210",
                "To": "whatsapp:+14155238886",
                "Body": "",
                "NumMedia": "1",
                "MediaUrl0": "https://api.twilio.com/media/audio123",
                "MediaContentType0": "audio/ogg",
            })

        assert response.status_code == 200
        assert "राम" in response.text
        mock_dl.assert_called_once()

    def test_audio_download_failure(self, whatsapp_app):
        mock_pipeline = MagicMock()

        with patch("core.api.gateway.pipeline", mock_pipeline), \
             patch("core.integrations.whatsapp._download_media", new_callable=AsyncMock) as mock_dl:
            mock_dl.side_effect = Exception("Network error")

            response = whatsapp_app.post("/webhook/whatsapp", data={
                "From": "whatsapp:+919876543210",
                "To": "whatsapp:+14155238886",
                "Body": "",
                "NumMedia": "1",
                "MediaUrl0": "https://api.twilio.com/media/audio123",
                "MediaContentType0": "audio/ogg",
            })

        assert response.status_code == 200
        assert "Could not process" in response.text


class TestWhatsAppPipelineNotReady:
    """Test behavior when pipeline is not initialized."""

    def test_pipeline_none(self, whatsapp_app):
        with patch("core.api.gateway.pipeline", None):
            response = whatsapp_app.post("/webhook/whatsapp", data={
                "From": "whatsapp:+919876543210",
                "To": "whatsapp:+14155238886",
                "Body": "hello",
                "NumMedia": "0",
            })

        assert response.status_code == 200
        assert "starting up" in response.text
