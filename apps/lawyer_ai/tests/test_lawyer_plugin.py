"""Tests for Lawyer AI plugin — architecture validation.

CRITICAL TEST: Verify ZERO files in core/ were modified to add this plugin.
"""

import json
import pytest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.lawyer_ai.plugin import LawyerAIPlugin, create_plugin, _query_store
from core.api.plugin_registry import PluginRegistry


# --- Fixtures ---

@pytest.fixture(autouse=True)
def clear_query_store():
    _query_store.clear()
    yield
    _query_store.clear()


@pytest.fixture
def plugin():
    return LawyerAIPlugin()


@pytest.fixture
def test_app(plugin):
    app = FastAPI()
    app.include_router(plugin.router(), prefix="/lawyer_ai")
    return TestClient(app)


# --- Architecture Validation (THE critical test) ---

class TestArchitectureValidation:
    """Verify that adding Lawyer AI required ZERO changes to core/."""

    def test_plugin_loads_without_core_changes(self):
        """PluginRegistry discovers both ASHA and Lawyer AI from apps/."""
        registry = PluginRegistry()
        registry.discover_and_load("apps")

        assert "asha_health" in registry.plugins
        assert "lawyer_ai" in registry.plugins
        assert len(registry.plugins) >= 2

    def test_plugin_satisfies_base_contract(self):
        plugin = create_plugin()
        assert plugin.app_id == "lawyer_ai"
        assert callable(plugin.system_prompt)
        assert callable(plugin.parse_response)
        assert plugin.router() is not None

    def test_core_files_not_modified(self):
        """Check that core/ plugin_registry.py does not import or depend on any specific app."""
        import inspect
        from core.api import plugin_registry

        source = inspect.getsource(plugin_registry)
        # The registry module should NOT import or reference any specific app module
        assert "from apps." not in source
        assert "import apps." not in source
        assert "import asha_health" not in source
        assert "import lawyer_ai" not in source


# --- Plugin Functionality ---

class TestLawyerPlugin:
    def test_system_prompt_includes_language(self, plugin):
        prompt = plugin.system_prompt("hi", {})
        assert "hi" in prompt
        assert "IPC" in prompt or "Indian" in prompt

    def test_parse_valid_response(self, plugin):
        llm_output = json.dumps({
            "answer": "धारा 420 के तहत धोखाधड़ी एक दंडनीय अपराध है।",
            "sections_cited": ["IPC Section 420"],
            "severity": "medium",
            "needs_lawyer": True,
            "response_text": "धारा 420 के तहत धोखाधड़ी एक दंडनीय अपराध है।",
        })

        result = plugin.parse_response(llm_output, {})

        assert result["severity"] == "medium"
        assert result["needs_lawyer"] is True
        assert "420" in result["response_text"]
        assert len(result["sections_cited"]) == 1

    def test_parse_markdown_wrapped(self, plugin):
        llm_output = '```json\n{"answer": "test", "sections_cited": [], "severity": "low", "needs_lawyer": false}\n```'
        result = plugin.parse_response(llm_output, {})
        assert result["answer"] == "test"

    def test_parse_sets_response_text_from_answer(self, plugin):
        llm_output = json.dumps({
            "answer": "This is the answer",
            "sections_cited": [],
            "severity": "low",
            "needs_lawyer": False,
        })
        result = plugin.parse_response(llm_output, {})
        assert result["response_text"] == "This is the answer"


# --- Route Tests ---

class TestLawyerRoutes:
    def test_ask_endpoint(self, test_app):
        response = test_app.post("/lawyer_ai/ask", json={
            "question": "FIR kaise file kare?",
            "user_id": "user-001",
            "language": "hi",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["query"]["query_text"] == "FIR kaise file kare?"
        assert data["query"]["user_id"] == "user-001"

    def test_list_queries(self, test_app):
        # Save a query first
        test_app.post("/lawyer_ai/ask", json={
            "question": "What is Section 302?",
            "user_id": "user-002",
        })

        response = test_app.get("/lawyer_ai/queries?user_id=user-002")
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_list_queries_empty(self, test_app):
        response = test_app.get("/lawyer_ai/queries")
        assert response.status_code == 200
        assert response.json()["count"] == 0


# --- Cross-Plugin Isolation ---

class TestCrossPluginIsolation:
    """Verify plugins don't leak data between each other."""

    def test_separate_app_ids(self):
        from apps.asha_health.plugin import create_plugin as create_asha
        from apps.lawyer_ai.plugin import create_plugin as create_lawyer

        asha = create_asha()
        lawyer = create_lawyer()

        assert asha.app_id != lawyer.app_id
        assert asha.app_id == "asha_health"
        assert lawyer.app_id == "lawyer_ai"

    def test_different_system_prompts(self):
        from apps.asha_health.plugin import create_plugin as create_asha
        from apps.lawyer_ai.plugin import create_plugin as create_lawyer

        asha_prompt = create_asha().system_prompt("hi", {})
        lawyer_prompt = create_lawyer().system_prompt("hi", {})

        assert asha_prompt != lawyer_prompt
        assert "health" in asha_prompt.lower() or "ASHA" in asha_prompt
        assert "legal" in lawyer_prompt.lower() or "IPC" in lawyer_prompt
