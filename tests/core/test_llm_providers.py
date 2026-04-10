"""Tests for LLM provider implementations.

Test IDs: PROV-001 through PROV-020
"""

import pytest
import httpx
import respx

from core.llm.providers.base import BaseLLMProvider
from core.llm.providers.ollama_provider import OllamaProvider
from core.llm.providers.groq_provider import GroqProvider
from core.llm.providers.gemini_provider import GeminiProvider
from core.llm.providers.claude_provider import ClaudeProvider
from core.llm.providers.sarvam_provider import SarvamProvider
from core.llm.providers.openai_compatible_provider import OpenAICompatibleProvider


# --- Base class contract tests ---

class TestBaseLLMProviderContract:
    """PROV-001: All providers implement BaseLLMProvider interface."""

    def test_ollama_is_base_provider(self):
        assert issubclass(OllamaProvider, BaseLLMProvider)

    def test_groq_is_base_provider(self):
        assert issubclass(GroqProvider, BaseLLMProvider)

    def test_gemini_is_base_provider(self):
        assert issubclass(GeminiProvider, BaseLLMProvider)

    def test_claude_is_base_provider(self):
        assert issubclass(ClaudeProvider, BaseLLMProvider)

    def test_sarvam_is_base_provider(self):
        assert issubclass(SarvamProvider, BaseLLMProvider)

    def test_openai_compat_is_base_provider(self):
        assert issubclass(OpenAICompatibleProvider, BaseLLMProvider)

    def test_all_have_provider_name(self):
        assert OllamaProvider.provider_name == "ollama"
        assert GroqProvider.provider_name == "groq"
        assert GeminiProvider.provider_name == "gemini"
        assert ClaudeProvider.provider_name == "claude"
        assert SarvamProvider.provider_name == "sarvam"
        assert OpenAICompatibleProvider.provider_name == "openai_compatible"


# --- Ollama Provider tests ---

class TestOllamaProvider:
    """PROV-002: Ollama provider wraps local Ollama server."""

    def test_default_url(self):
        p = OllamaProvider()
        assert "11434" in p._base_url

    def test_custom_url(self):
        p = OllamaProvider(base_url="http://custom:1234")
        assert p._base_url == "http://custom:1234"

    @pytest.mark.asyncio
    @respx.mock
    async def test_chat_success(self):
        respx.post("http://localhost:11434/api/chat").mock(
            return_value=httpx.Response(200, json={
                "message": {"content": "Hello from Ollama"},
                "model": "llama3.2",
            })
        )
        p = OllamaProvider(base_url="http://localhost:11434")
        result = await p.chat(
            [{"role": "user", "content": "hi"}], "llama3.2"
        )
        assert result == "Hello from Ollama"
        await p.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_is_healthy_ok(self):
        respx.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(200, json={"models": []})
        )
        p = OllamaProvider(base_url="http://localhost:11434")
        assert await p.is_healthy() is True
        await p.close()

    @pytest.mark.asyncio
    async def test_is_healthy_unreachable(self):
        p = OllamaProvider(base_url="http://localhost:99999")
        assert await p.is_healthy() is False

    def test_list_models_empty_initially(self):
        p = OllamaProvider()
        assert p.list_models() == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_models(self):
        respx.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(200, json={
                "models": [{"name": "llama3.2"}, {"name": "qwen3:1.7b"}]
            })
        )
        p = OllamaProvider(base_url="http://localhost:11434")
        models = await p.refresh_models()
        assert "llama3.2" in models
        assert "qwen3:1.7b" in models
        assert p.list_models() == models
        await p.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_generate(self):
        respx.post("http://localhost:11434/api/generate").mock(
            return_value=httpx.Response(200, json={"response": "raw output"})
        )
        p = OllamaProvider(base_url="http://localhost:11434")
        result = await p.generate("prompt", "llama3.2")
        assert result == "raw output"
        await p.close()


# --- Groq Provider tests ---

class TestGroqProvider:
    """PROV-003: Groq provider with rate limit handling."""

    def test_no_api_key_returns_empty(self):
        p = GroqProvider(api_key="")
        assert p._api_key == ""

    def test_list_models(self):
        p = GroqProvider(api_key="test")
        models = p.list_models()
        assert "llama-3.3-70b-versatile" in models
        assert "llama-3.1-8b-instant" in models

    @pytest.mark.asyncio
    @respx.mock
    async def test_chat_success(self):
        respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "choices": [{"message": {"content": "Hello from Groq"}}]
            })
        )
        p = GroqProvider(api_key="gsk_test")
        result = await p.chat(
            [{"role": "user", "content": "hi"}], "llama-3.3-70b-versatile"
        )
        assert result == "Hello from Groq"
        await p.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_is_healthy_with_key(self):
        respx.get("https://api.groq.com/openai/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        p = GroqProvider(api_key="gsk_test")
        assert await p.is_healthy() is True
        await p.close()

    @pytest.mark.asyncio
    async def test_is_healthy_without_key(self):
        p = GroqProvider(api_key="")
        assert await p.is_healthy() is False


# --- Gemini Provider tests ---

class TestGeminiProvider:
    """PROV-004: Gemini provider with message format conversion."""

    def test_list_models(self):
        p = GeminiProvider(api_key="test")
        models = p.list_models()
        assert "gemini-2.0-flash" in models

    def test_convert_messages_system_extraction(self):
        p = GeminiProvider(api_key="test")
        system, contents = p._convert_messages([
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ])
        assert system == "You are helpful"
        assert len(contents) == 1
        assert contents[0]["role"] == "user"

    def test_convert_messages_assistant_to_model(self):
        p = GeminiProvider(api_key="test")
        _, contents = p._convert_messages([
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ])
        assert contents[1]["role"] == "model"

    @pytest.mark.asyncio
    @respx.mock
    async def test_chat_success(self):
        respx.post(url__regex=r".*generativelanguage.*generateContent.*").mock(
            return_value=httpx.Response(200, json={
                "candidates": [{
                    "content": {"parts": [{"text": "Hello from Gemini"}]}
                }]
            })
        )
        p = GeminiProvider(api_key="test_key")
        result = await p.chat(
            [{"role": "user", "content": "hi"}], "gemini-2.0-flash"
        )
        assert result == "Hello from Gemini"
        await p.close()

    @pytest.mark.asyncio
    async def test_is_healthy_without_key(self):
        p = GeminiProvider(api_key="")
        assert await p.is_healthy() is False


# --- Claude Provider tests ---

class TestClaudeProvider:
    """PROV-005: Claude provider with Messages API format."""

    def test_list_models(self):
        p = ClaudeProvider(api_key="test")
        models = p.list_models()
        assert "claude-sonnet-4-20250514" in models

    def test_convert_messages_system_split(self):
        p = ClaudeProvider(api_key="test")
        system, msgs = p._convert_messages([
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hello"},
        ])
        assert system == "Be helpful"
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"

    @pytest.mark.asyncio
    @respx.mock
    async def test_chat_success(self):
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json={
                "content": [{"type": "text", "text": "Hello from Claude"}]
            })
        )
        p = ClaudeProvider(api_key="sk-test")
        result = await p.chat(
            [{"role": "user", "content": "hi"}], "claude-sonnet-4-20250514"
        )
        assert result == "Hello from Claude"
        await p.close()

    @pytest.mark.asyncio
    async def test_is_healthy_without_key(self):
        p = ClaudeProvider(api_key="")
        assert await p.is_healthy() is False


# --- Sarvam Provider tests ---

class TestSarvamProvider:
    """PROV-006: Sarvam provider for Hindi tasks."""

    def test_list_models(self):
        p = SarvamProvider(api_key="test")
        assert "sarvam-2b-v0.5" in p.list_models()

    @pytest.mark.asyncio
    @respx.mock
    async def test_chat_success(self):
        respx.post("https://api.sarvam.ai/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "choices": [{"message": {"content": "Namaste"}}]
            })
        )
        p = SarvamProvider(api_key="test")
        result = await p.chat(
            [{"role": "user", "content": "hi"}], "sarvam-2b-v0.5"
        )
        assert result == "Namaste"
        await p.close()

    @pytest.mark.asyncio
    async def test_is_healthy_without_key(self):
        p = SarvamProvider(api_key="")
        assert await p.is_healthy() is False


# --- OpenAI Compatible Provider tests ---

class TestOpenAICompatibleProvider:
    """PROV-007: Generic OpenAI-compatible provider."""

    def test_custom_base_url(self):
        p = OpenAICompatibleProvider(api_base="http://my-vllm:8080/v1")
        assert p._api_base == "http://my-vllm:8080/v1"

    def test_configured_models(self):
        p = OpenAICompatibleProvider(models=["my-model-7b"])
        assert p.list_models() == ["my-model-7b"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_chat_success(self):
        respx.post("http://localhost:8080/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "choices": [{"message": {"content": "Hello from vLLM"}}]
            })
        )
        p = OpenAICompatibleProvider(api_base="http://localhost:8080/v1")
        result = await p.chat(
            [{"role": "user", "content": "hi"}], "my-model"
        )
        assert result == "Hello from vLLM"
        await p.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_auto_discovers_models(self):
        respx.get("http://localhost:8080/v1/models").mock(
            return_value=httpx.Response(200, json={
                "data": [{"id": "model-a"}, {"id": "model-b"}]
            })
        )
        p = OpenAICompatibleProvider(api_base="http://localhost:8080/v1")
        assert await p.is_healthy() is True
        assert "model-a" in p.list_models()
        assert "model-b" in p.list_models()
        await p.close()
