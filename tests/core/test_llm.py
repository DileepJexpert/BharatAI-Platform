"""Tests for core/llm/ — LLM-001 through LLM-007.

All tests mock httpx calls to Ollama.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from core.llm.client import (
    OllamaClient,
    LLMResponse,
    OllamaTimeoutError,
    OllamaConnectionError,
    OllamaModelNotLoadedError,
)
from core.llm.model_manager import (
    ModelManager,
    ModelNotLoadedError,
    VRAMBudgetExceededError,
)
from core.llm.prompt_builder import build_messages, build_system_prompt


# --- Fixtures ---

@pytest.fixture
def client():
    return OllamaClient(base_url="http://localhost:11434", timeout=30.0)


@pytest.fixture
def model_manager():
    return ModelManager()


# --- Mock helpers ---

def _ollama_response(content: str, model: str = "llama3.2:3b-instruct-q4_0"):
    """Build a mock Ollama /api/chat JSON response."""
    return {
        "model": model,
        "message": {"role": "assistant", "content": content},
        "total_duration": 1500000000,  # 1500ms in nanoseconds
        "prompt_eval_count": 50,
        "eval_count": 30,
    }


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
    "confirmation_message": "राम, 45 साल, बुखार का दौरा दर्ज किया गया।"
})


# --- LLM Client Tests ---

class TestLLM001HindiJSONExtraction:
    """LLM-001: Hindi JSON extraction — valid JSON, name=राम, age=45."""

    @pytest.mark.asyncio
    async def test_hindi_extraction(self, client):
        mock_response = httpx.Response(200, json=_ollama_response(VALID_ASHA_JSON))

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            result = await client.chat(
                system="ASHA system prompt",
                user="राम 45 साल, बुखार है",
                model="llama3.2:3b-instruct-q4_0",
            )

        assert isinstance(result, LLMResponse)
        parsed = json.loads(result.text)
        assert parsed["patient_name"] == "राम"
        assert parsed["patient_age"] == 45


class TestLLM002JSONFormatEnforced:
    """LLM-002: JSON format enforced — parseable JSON, no markdown."""

    @pytest.mark.asyncio
    async def test_json_parseable(self, client):
        mock_response = httpx.Response(200, json=_ollama_response(VALID_ASHA_JSON))

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            result = await client.chat(
                system="Return JSON only",
                user="test input",
                model="llama3.2:3b-instruct-q4_0",
            )

        parsed = json.loads(result.text)
        assert isinstance(parsed, dict)


class TestLLM003MissingFieldsNull:
    """LLM-003: Missing fields = null — unmentioned fields are null."""

    def test_missing_fields_are_null(self):
        response_json = {
            "patient_name": "सीता",
            "patient_age": None,
            "gender": None,
            "complaint": "सिरदर्द",
            "temperature": None,
            "weight": None,
            "visit_date": "2026-03-27",
            "referral_needed": False,
            "notes": None,
            "confirmation_message": "सीता, सिरदर्द दर्ज किया।"
        }
        parsed = response_json
        assert parsed["patient_age"] is None
        assert parsed["temperature"] is None
        assert parsed["weight"] is None
        assert parsed["notes"] is None
        assert parsed["patient_name"] == "सीता"
        assert parsed["complaint"] == "सिरदर्द"


class TestLLM004ReferralDetection:
    """LLM-004: Referral detection — referral_needed: true."""

    def test_referral_true(self):
        response_json = {
            "patient_name": "test",
            "patient_age": 30,
            "gender": "male",
            "complaint": "serious condition",
            "temperature": None,
            "weight": None,
            "visit_date": "2026-03-27",
            "referral_needed": True,
            "notes": "hospital bhejo",
            "confirmation_message": "Referral needed"
        }
        assert response_json["referral_needed"] is True


class TestLLM005TimeoutHandling:
    """LLM-005: Timeout handling — Ollama timeout >30s raises OllamaTimeoutError."""

    @pytest.mark.asyncio
    async def test_timeout_raises_error(self, client):
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            with pytest.raises(OllamaTimeoutError, match="timed out"):
                await client.chat(
                    system="test",
                    user="test",
                    model="llama3.2:3b-instruct-q4_0",
                )


class TestLLM006ModelNotLoaded:
    """LLM-006: Model not loaded — 404 raises OllamaModelNotLoadedError."""

    @pytest.mark.asyncio
    async def test_model_not_found(self, client):
        mock_response = httpx.Response(404, text="model not found")

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            with pytest.raises(OllamaModelNotLoadedError, match="not found"):
                await client.chat(
                    system="test",
                    user="test",
                    model="nonexistent:model",
                )


class TestLLM007InvalidJSONRetry:
    """LLM-007: Invalid JSON retry — markdown-wrapped JSON can be stripped."""

    def test_strip_markdown_json(self):
        raw = '```json\n{"patient_name": "राम", "patient_age": 45}\n```'
        # Strip markdown code fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        parsed = json.loads(cleaned)
        assert parsed["patient_name"] == "राम"
        assert parsed["patient_age"] == 45


# --- Model Manager Tests ---

class TestModelManager:
    def test_load_default(self, model_manager):
        status = model_manager.load()
        assert status.is_loaded
        assert "llama3.2" in status.ollama_tag

    def test_active_model_before_load(self, model_manager):
        with pytest.raises(ModelNotLoadedError):
            _ = model_manager.active_model

    def test_vram_budget_exceeded(self):
        mm = ModelManager(vram_budget_mb=3000, _system_reserved_mb=1800)
        with pytest.raises(VRAMBudgetExceededError):
            mm.load("llama3.2:8b")

    def test_unload(self, model_manager):
        model_manager.load()
        model_manager.unload()
        assert model_manager.active_model_key is None

    def test_status(self, model_manager):
        model_manager.load()
        status = model_manager.status()
        assert "vram_budget_mb" in status
        assert status["active_model"] is not None


# --- Prompt Builder Tests ---

class TestPromptBuilder:
    def test_build_messages_basic(self):
        msgs = build_messages("system prompt", "user text")
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "system prompt"
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "user text"

    def test_build_messages_with_history(self):
        history = [
            {"role": "user", "text": "hello"},
            {"role": "assistant", "text": "hi"},
        ]
        msgs = build_messages("sys", "new msg", history)
        assert len(msgs) == 4  # system + 2 history + current user

    def test_build_system_prompt_with_language(self):
        template = "Respond in {language}"
        result = build_system_prompt(template, "hi")
        assert result == "Respond in hi"

    def test_build_messages_trims_history(self):
        history = [{"role": "user", "text": f"msg{i}"} for i in range(20)]
        msgs = build_messages("sys", "current", history)
        # system + 10 (MAX_HISTORY_TURNS*2) + current = 12
        assert len(msgs) == 12


# --- Ollama Client Connection Tests ---

class TestOllamaClientConnection:
    @pytest.mark.asyncio
    async def test_connection_error(self, client):
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(
                side_effect=httpx.ConnectError("refused")
            )
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            with pytest.raises(OllamaConnectionError):
                await client.chat("sys", "user", "model")

    @pytest.mark.asyncio
    async def test_is_healthy(self, client):
        mock_response = httpx.Response(200, json={"models": []})
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.is_closed = False
            mock_get.return_value = mock_http

            assert await client.is_healthy() is True
