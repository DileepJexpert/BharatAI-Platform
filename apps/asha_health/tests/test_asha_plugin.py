"""Tests for ASHA Health plugin — ASHA-001 through ASHA-008.

Tests the plugin's parse_response, system_prompt, routes, and domain logic.
LLM is not called — we test the parsing/routing logic directly.
"""

import json
import pytest
from datetime import date
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.asha_health.plugin import (
    AshaHealthPlugin,
    create_plugin,
    _visit_store,
    _save_visit,
    _check_duplicate,
)
from apps.asha_health.nhm_client import NHMClient
from core.api.plugin_registry import PluginRegistry


# --- Fixtures ---

@pytest.fixture(autouse=True)
def clear_visit_store():
    """Clear the in-memory visit store between tests."""
    _visit_store.clear()
    yield
    _visit_store.clear()


@pytest.fixture
def plugin():
    return AshaHealthPlugin()


@pytest.fixture
def test_app(plugin):
    """FastAPI app with ASHA routes for endpoint testing."""
    app = FastAPI()
    app.include_router(plugin.router(), prefix="/asha_health")
    return TestClient(app)


# --- ASHA-001: Basic visit recording ---

class TestASHA001BasicVisit:
    """ASHA-001: 'राम, 45 साल, बुखार है' → name=राम, age=45, complaint=बुखार."""

    def test_parse_basic_visit(self, plugin):
        llm_output = json.dumps({
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

        result = plugin.parse_response(llm_output, {})

        assert result["patient_name"] == "राम"
        assert result["patient_age"] == 45
        assert result["complaint"] == "बुखार"
        assert result["gender"] == "male"
        assert result["referral_needed"] is False


# --- ASHA-002: Age with suffix ---

class TestASHA002AgeSuffix:
    """ASHA-002: 'रमा देवी, पचास साल की, खांसी' → name=रमा देवी, age=50."""

    def test_parse_age_number(self, plugin):
        llm_output = json.dumps({
            "patient_name": "रमा देवी",
            "patient_age": 50,
            "gender": "female",
            "complaint": "खांसी",
            "temperature": None,
            "weight": None,
            "visit_date": "2026-03-27",
            "referral_needed": False,
            "notes": None,
            "confirmation_message": "रमा देवी, 50 साल, खांसी दर्ज की गई।"
        })

        result = plugin.parse_response(llm_output, {})

        assert result["patient_name"] == "रमा देवी"
        assert result["patient_age"] == 50
        assert result["complaint"] == "खांसी"


# --- ASHA-003: Referral trigger ---

class TestASHA003ReferralTrigger:
    """ASHA-003: 'bahut serious, hospital bhejo' → referral_needed=true."""

    def test_referral_detection(self, plugin):
        llm_output = json.dumps({
            "patient_name": "सीता",
            "patient_age": 35,
            "gender": "female",
            "complaint": "bahut serious condition",
            "temperature": None,
            "weight": None,
            "visit_date": "2026-03-27",
            "referral_needed": True,
            "notes": "hospital bhejo",
            "confirmation_message": "सीता को अस्पताल रेफर किया गया।"
        })

        result = plugin.parse_response(llm_output, {})

        assert result["referral_needed"] is True


# --- ASHA-004: Temperature F→C ---

class TestASHA004TemperatureConversion:
    """ASHA-004: 'bukhaar hai, 103 degree' → temperature=39.4 (F→C)."""

    def test_fahrenheit_to_celsius(self, plugin):
        llm_output = json.dumps({
            "patient_name": "राम",
            "patient_age": 45,
            "gender": "male",
            "complaint": "बुखार",
            "temperature": 103,
            "weight": None,
            "visit_date": "2026-03-27",
            "referral_needed": False,
            "notes": None,
            "confirmation_message": "राम, बुखार 39.4°C दर्ज किया।"
        })

        result = plugin.parse_response(llm_output, {})

        assert result["temperature"] == 39.4

    def test_celsius_not_converted(self, plugin):
        """Temperature already in Celsius (<= 50) should not be converted."""
        llm_output = json.dumps({
            "patient_name": "test",
            "patient_age": 30,
            "gender": "male",
            "complaint": "fever",
            "temperature": 38.5,
            "weight": None,
            "visit_date": "2026-03-27",
            "referral_needed": False,
            "notes": None,
            "confirmation_message": "test"
        })

        result = plugin.parse_response(llm_output, {})

        assert result["temperature"] == 38.5


# --- ASHA-005: Response language ---

class TestASHA005ResponseLanguage:
    """ASHA-005: Hindi input → confirmation_message is in Hindi."""

    def test_system_prompt_includes_language(self, plugin):
        prompt = plugin.system_prompt("hi", {})
        assert "hi" in prompt

    def test_confirmation_in_hindi(self, plugin):
        llm_output = json.dumps({
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

        result = plugin.parse_response(llm_output, {})

        # Confirmation message should contain Hindi characters
        assert any(0x0900 <= ord(c) <= 0x097F for c in result["confirmation_message"])


# --- ASHA-006: Save to DB (in-memory for MVP) ---

class TestASHA006SaveToDB:
    """ASHA-006: Valid visit data → saved with sync_status='pending'."""

    def test_save_visit_endpoint(self, test_app):
        response = test_app.post("/asha_health/confirm", json={
            "visit_data": {
                "patient_name": "राम",
                "patient_age": 45,
                "complaint": "बुखार",
                "visit_date": "2026-03-27",
                "referral_needed": False,
            },
            "worker_id": "worker-001",
            "raw_transcript": "राम 45 साल बुखार है",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Visit saved"
        assert data["visit"]["sync_status"] == "pending"
        assert data["visit"]["patient_name"] == "राम"
        assert data["visit"]["worker_id"] == "worker-001"
        assert data["visit"]["raw_transcript"] == "राम 45 साल बुखार है"

    def test_list_visits(self, test_app):
        # Save a visit first
        test_app.post("/asha_health/confirm", json={
            "visit_data": {"patient_name": "राम", "complaint": "बुखार"},
            "worker_id": "worker-001",
        })

        response = test_app.get("/asha_health/visits?worker_id=worker-001")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["visits"][0]["patient_name"] == "राम"


# --- ASHA-007: Offline queue ---

class TestASHA007OfflineQueue:
    """ASHA-007: NHM API unavailable → saved locally, no error to user."""

    @pytest.mark.asyncio
    async def test_nhm_unavailable_no_error(self):
        nhm = NHMClient()
        assert nhm.is_available is False

        visit = {"id": "v-001", "patient_name": "राम", "sync_status": "pending"}
        result = await nhm.sync_visit(visit)

        # Visit should remain pending, no exception
        assert result["sync_status"] == "pending"

    @pytest.mark.asyncio
    async def test_sync_all_pending(self):
        nhm = NHMClient()
        pending = [
            {"id": "v-001", "sync_status": "pending"},
            {"id": "v-002", "sync_status": "pending"},
        ]

        result = await nhm.sync_all_pending(pending)

        assert result["synced"] == 0
        assert result["pending"] == 2
        assert result["failed"] == 0

    def test_save_endpoint_works_when_nhm_down(self, test_app):
        """Saving via API should succeed even when NHM is unreachable."""
        response = test_app.post("/asha_health/confirm", json={
            "visit_data": {"patient_name": "सीता", "complaint": "ताप"},
            "worker_id": "worker-002",
        })

        assert response.status_code == 200
        assert response.json()["visit"]["sync_status"] == "pending"


# --- ASHA-008: Duplicate prevention ---

class TestASHA008DuplicatePrevention:
    """ASHA-008: Same worker+patient+day → warns, asks confirm."""

    def test_duplicate_warning(self, test_app):
        visit_data = {
            "patient_name": "राम",
            "patient_age": 45,
            "complaint": "बुखार",
            "visit_date": "2026-03-27",
        }

        # First save
        resp1 = test_app.post("/asha_health/confirm", json={
            "visit_data": visit_data,
            "worker_id": "worker-dup",
        })
        assert resp1.status_code == 200
        assert resp1.json()["message"] == "Visit saved"

        # Second save — same worker, patient, date
        resp2 = test_app.post("/asha_health/confirm", json={
            "visit_data": visit_data,
            "worker_id": "worker-dup",
        })
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["warning"] == "duplicate"
        assert "already exists" in data2["message"]

    def test_different_patient_no_warning(self, test_app):
        # Save for patient A
        test_app.post("/asha_health/confirm", json={
            "visit_data": {"patient_name": "राम", "visit_date": "2026-03-27"},
            "worker_id": "worker-x",
        })

        # Save for patient B — no duplicate warning
        resp = test_app.post("/asha_health/confirm", json={
            "visit_data": {"patient_name": "सीता", "visit_date": "2026-03-27"},
            "worker_id": "worker-x",
        })
        assert resp.json()["message"] == "Visit saved"


# --- Plugin auto-load verification ---

class TestPluginAutoLoad:
    """Verify plugin auto-loads via PluginRegistry."""

    def test_create_plugin_factory(self):
        plugin = create_plugin()
        assert isinstance(plugin, AshaHealthPlugin)
        assert plugin.app_id == "asha_health"

    def test_registry_discovers_asha(self):
        registry = PluginRegistry()
        registry.discover_and_load("apps")
        assert "asha_health" in registry.plugins

    def test_plugin_satisfies_contract(self):
        plugin = create_plugin()
        assert plugin.app_id == "asha_health"
        assert callable(plugin.system_prompt)
        assert callable(plugin.parse_response)
        assert plugin.router() is not None


# --- Markdown stripping ---

class TestMarkdownStripping:
    """parse_response handles markdown-wrapped JSON from LLM."""

    def test_strip_markdown_fences(self, plugin):
        llm_output = '```json\n{"patient_name": "राम", "patient_age": 45, "complaint": "बुखार", "referral_needed": false, "confirmation_message": "test"}\n```'

        result = plugin.parse_response(llm_output, {})
        assert result["patient_name"] == "राम"

    def test_default_visit_date(self, plugin):
        """Missing visit_date defaults to today."""
        llm_output = json.dumps({
            "patient_name": "test",
            "patient_age": 30,
            "complaint": "cough",
            "visit_date": None,
            "referral_needed": False,
            "confirmation_message": "test",
        })

        result = plugin.parse_response(llm_output, {})
        assert result["visit_date"] == date.today().isoformat()
