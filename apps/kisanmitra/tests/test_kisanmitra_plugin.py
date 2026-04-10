"""Tests for KisanMitra plugin — plugin contract, routes, tools, scrapers."""

import pytest
from unittest.mock import AsyncMock, patch

from apps.kisanmitra.plugin import KisanMitraPlugin, create_plugin


class TestKMPluginContract:
    """Test that KisanMitra satisfies BasePlugin contract."""

    def test_create_plugin_factory(self):
        plugin = create_plugin()
        assert plugin is not None
        assert isinstance(plugin, KisanMitraPlugin)

    def test_app_id(self):
        plugin = create_plugin()
        assert plugin.app_id == "kisanmitra"

    def test_system_prompt(self):
        plugin = create_plugin()
        prompt = plugin.system_prompt("hi", {})
        assert "KisanMitra" in prompt or "किसानमित्र" in prompt
        assert "Hindi" in prompt or "hi" in prompt.lower()

    def test_system_prompt_english(self):
        plugin = create_plugin()
        prompt = plugin.system_prompt("en", {})
        assert "KisanMitra" in prompt

    def test_system_prompt_with_context(self):
        plugin = create_plugin()
        prompt = plugin.system_prompt("hi", {"user_profile": {"name": "Ramu"}})
        assert isinstance(prompt, str)

    def test_parse_response_text(self):
        plugin = create_plugin()
        result = plugin.parse_response("Namaste! Main KisanMitra hun.", {})
        assert "response_text" in result
        assert "KisanMitra" in result["response_text"]

    def test_parse_response_json(self):
        plugin = create_plugin()
        llm_output = 'Here are schemes: {"schemes": ["PM-KISAN"], "action": "list"}'
        result = plugin.parse_response(llm_output, {})
        assert "schemes" in result

    def test_router_returns_api_router(self):
        from fastapi import APIRouter
        plugin = create_plugin()
        router = plugin.router()
        assert isinstance(router, APIRouter)

    def test_router_cached(self):
        plugin = create_plugin()
        r1 = plugin.router()
        r2 = plugin.router()
        assert r1 is r2

    def test_on_startup(self):
        plugin = create_plugin()
        # Should not raise
        plugin.on_startup()

    def test_on_session_start(self):
        plugin = create_plugin()
        session = {"session_id": "test", "app_id": "kisanmitra"}
        result = plugin.on_session_start(session)
        assert "app_state" in result
        assert "last_commodity" in result["app_state"]


class TestKMRoutes:
    """Test KisanMitra API routes via TestClient."""

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        plugin = create_plugin()
        app.include_router(plugin.router(), prefix="/kisanmitra")
        return TestClient(app)

    def test_help_endpoint(self, client):
        resp = client.get("/kisanmitra/help")
        assert resp.status_code == 200
        data = resp.json()
        assert "help" in data

    def test_help_endpoint_hindi(self, client):
        resp = client.get("/kisanmitra/help?language=hi")
        assert resp.status_code == 200
        data = resp.json()
        assert "किसानमित्र" in data["help"]

    def test_help_endpoint_english(self, client):
        resp = client.get("/kisanmitra/help?language=en")
        data = resp.json()
        assert "KisanMitra" in data["help"]

    def test_scheme_search(self, client):
        resp = client.post(
            "/kisanmitra/schemes/search",
            json={"query": "farmer loan subsidy", "language": "en"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "schemes" in data
        assert data["count"] > 0

    def test_scheme_search_sector_filter(self, client):
        resp = client.post(
            "/kisanmitra/schemes/search",
            json={"query": "dairy", "sector": "dairy"},
        )
        data = resp.json()
        assert "schemes" in data

    def test_mandi_price(self, client):
        resp = client.post(
            "/kisanmitra/mandi/price",
            json={"commodity": "tamatar"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["commodity"] == "Tomato"
        assert "modal_price" in data

    def test_mandi_price_hindi_commodity(self, client):
        resp = client.post(
            "/kisanmitra/mandi/price",
            json={"commodity": "गेहूं", "market": "Indore"},
        )
        data = resp.json()
        assert data["commodity"] == "Wheat"
        assert data["market"] == "Indore"

    def test_mandi_compare(self, client):
        resp = client.post(
            "/kisanmitra/mandi/compare",
            json={"commodity": "Wheat"},
        )
        data = resp.json()
        assert "markets" in data
        assert len(data["markets"]) > 0

    def test_mandi_predict(self, client):
        resp = client.post(
            "/kisanmitra/mandi/predict",
            json={"commodity": "Tomato", "market": "Indore"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "commodity" in data

    def test_loan_emi(self, client):
        resp = client.post(
            "/kisanmitra/loan/emi",
            json={"principal": 500000, "annual_rate": 10.0, "tenure_years": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "emi_monthly" in data
        assert data["emi_monthly"] > 0

    def test_loan_eligibility(self, client):
        resp = client.post(
            "/kisanmitra/loan/eligibility",
            json={"language": "hi"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "loans" in data
        assert data["count"] > 0

    def test_loan_eligibility_filtered(self, client):
        resp = client.post(
            "/kisanmitra/loan/eligibility",
            json={"loan_type": "KCC"},
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["loans"][0]["loan_code"] == "KCC"
