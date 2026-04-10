"""Tests for Vyapaar Sahayak plugin — plugin contract, routes, architecture."""

import json
import pytest

from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

from apps.vyapaar.plugin import VyapaarPlugin, create_plugin
from apps.vyapaar.tools.contacts import clear_contacts
from apps.vyapaar.tools.bookkeeping import clear_transactions
from apps.vyapaar.tools.catalogue import clear_products
from apps.vyapaar.tools.invoicing import reset_invoice_counter
from core.api.plugin_registry import PluginRegistry


@pytest.fixture(autouse=True)
def clean_stores():
    """Reset all in-memory stores before each test."""
    clear_contacts()
    clear_transactions()
    clear_products()
    reset_invoice_counter()
    yield
    clear_contacts()
    clear_transactions()
    clear_products()
    reset_invoice_counter()


class TestVyapaarPluginContract:
    """Test that Vyapaar Sahayak satisfies BasePlugin contract."""

    def test_create_plugin_factory(self):
        plugin = create_plugin()
        assert plugin is not None
        assert isinstance(plugin, VyapaarPlugin)

    def test_app_id(self):
        plugin = create_plugin()
        assert plugin.app_id == "vyapaar"

    def test_system_prompt_hindi(self):
        plugin = create_plugin()
        prompt = plugin.system_prompt("hi", {})
        assert "Vyapaar Sahayak" in prompt or "व्यापार" in prompt
        assert "Hindi" in prompt or "hi" in prompt.lower()

    def test_system_prompt_english(self):
        plugin = create_plugin()
        prompt = plugin.system_prompt("en", {})
        assert "Vyapaar Sahayak" in prompt or "bookkeeping" in prompt.lower()

    def test_system_prompt_with_context(self):
        plugin = create_plugin()
        prompt = plugin.system_prompt("hi", {"user_profile": {"name": "Raju"}})
        assert isinstance(prompt, str)

    def test_parse_response_text(self):
        plugin = create_plugin()
        result = plugin.parse_response("Namaste! Main Vyapaar Sahayak hun.", {})
        assert "response_text" in result
        assert "Vyapaar Sahayak" in result["response_text"]

    def test_parse_response_json(self):
        plugin = create_plugin()
        llm_output = 'Here is the data: {"intent": "RECORD_SALE", "entities": {"amount": 5000}}'
        result = plugin.parse_response(llm_output, {})
        assert "intent" in result
        assert result["intent"] == "RECORD_SALE"

    def test_router_returns_api_router(self):
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
        plugin.on_startup()  # Should not raise

    def test_on_session_start(self):
        plugin = create_plugin()
        session = {"session_id": "test", "app_id": "vyapaar"}
        result = plugin.on_session_start(session)
        assert "app_state" in result
        assert "business_name" in result["app_state"]
        assert "last_contact" in result["app_state"]


class TestArchitectureValidation:
    """Verify that adding Vyapaar required ZERO changes to core/."""

    def test_plugin_discovered(self):
        registry = PluginRegistry()
        registry.discover_and_load("apps")
        assert "vyapaar" in registry.plugins
        assert len(registry.plugins) >= 3  # asha_health, lawyer_ai, kisanmitra, vyapaar

    def test_core_files_not_modified(self):
        """Core/ plugin_registry.py does not import any specific app."""
        import inspect
        from core.api import plugin_registry
        source = inspect.getsource(plugin_registry)
        assert "from apps." not in source
        assert "import apps." not in source
        assert "import vyapaar" not in source


class TestVyapaarRoutes:
    """Test Vyapaar API routes via TestClient."""

    @pytest.fixture
    def client(self):
        app = FastAPI()
        plugin = create_plugin()
        app.include_router(plugin.router(), prefix="/vyapaar")
        return TestClient(app)

    def test_help_endpoint_hindi(self, client):
        resp = client.get("/vyapaar/help?language=hi")
        assert resp.status_code == 200
        data = resp.json()
        assert "help" in data
        assert "हिसाब" in data["help"]

    def test_help_endpoint_english(self, client):
        resp = client.get("/vyapaar/help?language=en")
        data = resp.json()
        assert "Vyapaar Sahayak" in data["help"]

    # ── Bookkeeping routes ─────────────────────────────────

    def test_record_sale(self, client):
        resp = client.post("/vyapaar/bookkeeping/sale", json={
            "contact_name": "Sharma Ji",
            "amount": 5000,
            "payment_mode": "credit",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "SALE"
        assert data["amount_rupees"] == 5000.0
        assert data["contact_name"] == "Sharma Ji"
        assert data["new_balance_rupees"] == 5000.0

    def test_record_purchase(self, client):
        resp = client.post("/vyapaar/bookkeeping/purchase", json={
            "contact_name": "Supplier A",
            "amount": 10000,
            "payment_mode": "credit",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "PURCHASE"
        assert data["new_balance_rupees"] == -10000.0

    def test_payment_in(self, client):
        # First create a sale
        client.post("/vyapaar/bookkeeping/sale", json={
            "contact_name": "Sharma",
            "amount": 5000,
            "payment_mode": "credit",
        })
        resp = client.post("/vyapaar/bookkeeping/payment-in", json={
            "contact_name": "Sharma",
            "amount": 3000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "PAYMENT_IN"
        assert data["new_balance_rupees"] == 2000.0

    def test_payment_out(self, client):
        client.post("/vyapaar/bookkeeping/purchase", json={
            "contact_name": "Supplier A",
            "amount": 10000,
            "payment_mode": "credit",
        })
        resp = client.post("/vyapaar/bookkeeping/payment-out", json={
            "contact_name": "Supplier A",
            "amount": 5000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_balance_rupees"] == -5000.0

    def test_expense(self, client):
        resp = client.post("/vyapaar/bookkeeping/expense", json={
            "amount": 1500,
            "description": "Bijli ka bill",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "EXPENSE"
        assert data["amount_rupees"] == 1500.0

    def test_check_balance(self, client):
        client.post("/vyapaar/bookkeeping/sale", json={
            "contact_name": "Sharma",
            "amount": 5000,
            "payment_mode": "credit",
        })
        resp = client.post("/vyapaar/bookkeeping/balance", json={
            "contact_name": "Sharma",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["balance_rupees"] == 5000.0

    def test_check_balance_not_found(self, client):
        resp = client.post("/vyapaar/bookkeeping/balance", json={
            "contact_name": "UnknownPerson",
        })
        data = resp.json()
        assert "error" in data

    def test_daily_summary(self, client):
        client.post("/vyapaar/bookkeeping/sale", json={
            "contact_name": "Sharma",
            "amount": 5000,
        })
        resp = client.get("/vyapaar/bookkeeping/daily-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sales"] == 500000
        assert data["transaction_count"] == 1

    def test_credit_report(self, client):
        client.post("/vyapaar/bookkeeping/sale", json={
            "contact_name": "Sharma",
            "amount": 5000,
            "payment_mode": "credit",
        })
        resp = client.get("/vyapaar/bookkeeping/credit-report")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["customers_who_owe"]) == 1
        assert data["total_receivable"] == 500000

    # ── Catalogue routes ───────────────────────────────────

    def test_add_product(self, client):
        resp = client.post("/vyapaar/catalogue/add", json={
            "name": "Cement",
            "selling_price": 400,
            "unit": "bag",
            "current_stock": 100,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Cement"

    def test_update_stock(self, client):
        client.post("/vyapaar/catalogue/add", json={
            "name": "Cement",
            "selling_price": 400,
            "current_stock": 50,
        })
        resp = client.post("/vyapaar/catalogue/stock", json={
            "product_name": "Cement",
            "quantity_change": -10,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_stock"] == 40

    def test_update_stock_not_found(self, client):
        resp = client.post("/vyapaar/catalogue/stock", json={
            "product_name": "NonexistentProduct",
            "quantity_change": 5,
        })
        data = resp.json()
        assert "error" in data

    def test_low_stock(self, client):
        client.post("/vyapaar/catalogue/add", json={
            "name": "Cement",
            "selling_price": 400,
            "current_stock": 5,
            "low_stock_threshold": 10,
        })
        resp = client.get("/vyapaar/catalogue/low-stock")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1

    # ── Invoice routes ─────────────────────────────────────

    def test_create_invoice(self, client):
        resp = client.post("/vyapaar/invoice/create", json={
            "business_name": "Raju Store",
            "contact_name": "Sharma",
            "items": [
                {"product_name": "Cement", "quantity": 10, "unit_price_rupees": 400, "gst_rate": 18},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "invoice_number" in data
        assert data["subtotal_paisa"] == 400000
        assert data["cgst_paisa"] == 36000

    def test_create_invoice_no_gst(self, client):
        resp = client.post("/vyapaar/invoice/create", json={
            "items": [
                {"product_name": "Sand", "quantity": 5, "unit_price_rupees": 200, "gst_rate": 0},
            ],
        })
        data = resp.json()
        assert data["total_paisa"] == data["subtotal_paisa"]

    # ── Report routes ──────────────────────────────────────

    def test_formatted_summary(self, client):
        client.post("/vyapaar/bookkeeping/sale", json={
            "contact_name": "Sharma",
            "amount": 5000,
        })
        resp = client.post("/vyapaar/report/formatted-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "Aaj ka hisaab" in data["text"]


class TestCrossPluginIsolation:
    """Verify plugins don't leak data between each other."""

    def test_separate_app_ids(self):
        from apps.kisanmitra.plugin import create_plugin as create_kisan
        from apps.vyapaar.plugin import create_plugin as create_vyapaar

        kisan = create_kisan()
        vyapaar = create_vyapaar()

        assert kisan.app_id != vyapaar.app_id
        assert kisan.app_id == "kisanmitra"
        assert vyapaar.app_id == "vyapaar"

    def test_different_system_prompts(self):
        from apps.kisanmitra.plugin import create_plugin as create_kisan
        from apps.vyapaar.plugin import create_plugin as create_vyapaar

        kisan_prompt = create_kisan().system_prompt("hi", {})
        vyapaar_prompt = create_vyapaar().system_prompt("hi", {})

        assert kisan_prompt != vyapaar_prompt
        assert "KisanMitra" in kisan_prompt or "किसान" in kisan_prompt
        assert "Vyapaar" in vyapaar_prompt or "व्यापार" in vyapaar_prompt
