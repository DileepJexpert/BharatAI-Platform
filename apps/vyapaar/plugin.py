"""Vyapaar Sahayak plugin — implements BasePlugin for small business bookkeeping.

Provides:
- Bookkeeping: sales, purchases, payments, expenses
- Contact management with fuzzy Hindi name matching
- Product catalogue and stock tracking
- GST-compliant invoice generation
- Reports: daily summary, credit report, transaction history
- Hindi/English/Hinglish bilingual support

Uses core/ frameworks:
- BaseSupervisor for multi-agent intent routing
- VoicePipeline for Hinglish voice transcription
"""

import json
import logging
import re
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from core.api.plugin_registry import BasePlugin
from core.llm.prompt_builder import build_system_prompt

from .prompts import SYSTEM_PROMPT, HELP_TEXT_HI, HELP_TEXT_EN

logger = logging.getLogger("vyapaar")


# --- Pydantic request models ---

class SaleRequest(BaseModel):
    contact_name: str
    amount: float
    payment_mode: str = "credit"
    description: str | None = None
    product_name: str | None = None
    quantity: float | None = None
    unit: str | None = None


class PurchaseRequest(BaseModel):
    contact_name: str
    amount: float
    payment_mode: str = "credit"
    description: str | None = None
    product_name: str | None = None
    quantity: float | None = None
    unit: str | None = None


class PaymentRequest(BaseModel):
    contact_name: str
    amount: float
    payment_mode: str = "cash"


class ExpenseRequest(BaseModel):
    amount: float
    description: str | None = None


class BalanceRequest(BaseModel):
    contact_name: str


class ProductRequest(BaseModel):
    name: str
    selling_price: float
    unit: str = "piece"
    current_stock: float = 0
    low_stock_threshold: float | None = None
    gst_rate: float = 0


class StockUpdateRequest(BaseModel):
    product_name: str
    quantity_change: float


class InvoiceRequest(BaseModel):
    contact_name: str = ""
    business_name: str = ""
    gstin: str = ""
    items: list[dict]


class EMIRequest(BaseModel):
    principal: float
    annual_rate: float
    tenure_years: int


# --- Plugin ---

class VyapaarPlugin(BasePlugin):
    """Vyapaar Sahayak plugin for small business bookkeeping."""

    def __init__(self) -> None:
        self._router: APIRouter | None = None

    @property
    def app_id(self) -> str:
        return "vyapaar"

    def system_prompt(self, language: str, context: dict[str, Any]) -> str:
        """Return Vyapaar Sahayak system prompt formatted with language."""
        user_profile = context.get("user_profile", {})
        name = user_profile.get("name", "")
        return build_system_prompt(
            SYSTEM_PROMPT,
            language,
            extra_context={"user_name": name},
        )

    def parse_response(self, llm_output: str, context: dict[str, Any]) -> dict[str, Any]:
        """Parse LLM output — handles conversational text and structured data."""
        logger.info("[VS] Raw LLM output: %s", llm_output[:500])

        data = _extract_json(llm_output)
        if data and any(k in data for k in ("intent", "entities", "transaction", "invoice", "action")):
            logger.info("[VS] Structured data found: %s", list(data.keys()))
            clean_text = _strip_json_block(llm_output).strip()
            data["response_text"] = clean_text or data.get("response", llm_output.strip())
            return data

        logger.info("[VS] Conversational response")
        return {"response_text": llm_output.strip()}

    def router(self) -> APIRouter:
        """Return Vyapaar-specific routes."""
        if self._router is not None:
            return self._router

        router = APIRouter()

        @router.get("/help")
        async def help_text(language: str = "hi") -> dict[str, str]:
            """Return help text listing Vyapaar Sahayak capabilities."""
            text = HELP_TEXT_HI if language == "hi" else HELP_TEXT_EN
            return {"help": text, "language": language}

        # ── Bookkeeping routes ─────────────────────────────────

        @router.post("/bookkeeping/sale")
        async def record_sale(request: SaleRequest) -> dict[str, Any]:
            """Record a sale transaction."""
            from .tools.bookkeeping import record_sale as do_sale
            result = do_sale(
                contact_name=request.contact_name,
                amount_rupees=request.amount,
                payment_mode=request.payment_mode,
                description=request.description,
                product_name=request.product_name,
                quantity=request.quantity,
                unit=request.unit,
            )
            return _txn_response(result)

        @router.post("/bookkeeping/purchase")
        async def record_purchase(request: PurchaseRequest) -> dict[str, Any]:
            """Record a purchase transaction."""
            from .tools.bookkeeping import record_purchase as do_purchase
            result = do_purchase(
                contact_name=request.contact_name,
                amount_rupees=request.amount,
                payment_mode=request.payment_mode,
                description=request.description,
                product_name=request.product_name,
                quantity=request.quantity,
                unit=request.unit,
            )
            return _txn_response(result)

        @router.post("/bookkeeping/payment-in")
        async def payment_in(request: PaymentRequest) -> dict[str, Any]:
            """Record incoming payment from customer."""
            from .tools.bookkeeping import record_payment_in
            result = record_payment_in(
                contact_name=request.contact_name,
                amount_rupees=request.amount,
                payment_mode=request.payment_mode,
            )
            return _txn_response(result)

        @router.post("/bookkeeping/payment-out")
        async def payment_out(request: PaymentRequest) -> dict[str, Any]:
            """Record outgoing payment to supplier."""
            from .tools.bookkeeping import record_payment_out
            result = record_payment_out(
                contact_name=request.contact_name,
                amount_rupees=request.amount,
                payment_mode=request.payment_mode,
            )
            return _txn_response(result)

        @router.post("/bookkeeping/expense")
        async def expense(request: ExpenseRequest) -> dict[str, Any]:
            """Record a business expense."""
            from .tools.bookkeeping import record_expense
            result = record_expense(
                amount_rupees=request.amount,
                description=request.description,
            )
            return _txn_response(result)

        @router.post("/bookkeeping/balance")
        async def check_balance(request: BalanceRequest) -> dict[str, Any]:
            """Check balance for a contact."""
            from .tools.bookkeeping import get_contact_balance
            balance = get_contact_balance(request.contact_name)
            if balance is None:
                return {"error": f"Contact '{request.contact_name}' not found"}
            return balance

        @router.get("/bookkeeping/daily-summary")
        async def daily_summary() -> dict[str, Any]:
            """Get today's daily summary."""
            from .tools.bookkeeping import get_daily_summary
            summary = get_daily_summary()
            return {
                "date": summary.date,
                "total_sales": summary.total_sales,
                "total_purchases": summary.total_purchases,
                "total_payments_in": summary.total_payments_in,
                "total_payments_out": summary.total_payments_out,
                "total_expenses": summary.total_expenses,
                "net_position": summary.net_position,
                "transaction_count": summary.transaction_count,
                "top_credit_customers": summary.top_credit_customers,
                "total_outstanding": summary.total_outstanding,
            }

        @router.get("/bookkeeping/credit-report")
        async def credit_report() -> dict[str, Any]:
            """Get credit report (who owes what)."""
            from .tools.bookkeeping import get_credit_report
            report = get_credit_report()
            return {
                "customers_who_owe": report.customers_who_owe,
                "total_receivable": report.total_receivable,
                "suppliers_we_owe": report.suppliers_we_owe,
                "total_payable": report.total_payable,
            }

        # ── Catalogue routes ───────────────────────────────────

        @router.post("/catalogue/add")
        async def add_product(request: ProductRequest) -> dict[str, Any]:
            """Add a product to the catalogue."""
            from .tools.catalogue import add_product as do_add
            product = do_add(
                name=request.name,
                selling_price_rupees=request.selling_price,
                unit=request.unit,
                current_stock=request.current_stock,
                low_stock_threshold=request.low_stock_threshold,
                gst_rate=request.gst_rate,
            )
            return {
                "product_id": product.id,
                "name": product.name,
                "selling_price_display": f"₹{request.selling_price}",
                "unit": product.unit,
                "stock": product.current_stock,
            }

        @router.post("/catalogue/stock")
        async def update_stock(request: StockUpdateRequest) -> dict[str, Any]:
            """Update stock for a product."""
            from .tools.catalogue import update_stock as do_update
            result = do_update(request.product_name, request.quantity_change)
            if result is None:
                return {"error": f"Product '{request.product_name}' not found"}
            return {
                "product": result.product.name,
                "new_stock": result.new_stock,
                "unit": result.product.unit,
                "is_low_stock": result.is_low_stock,
            }

        @router.get("/catalogue/low-stock")
        async def low_stock() -> dict[str, Any]:
            """Get low-stock products."""
            from .tools.catalogue import get_low_stock_products
            products = get_low_stock_products()
            return {
                "products": [
                    {"name": p.name, "stock": p.current_stock, "threshold": p.low_stock_threshold, "unit": p.unit}
                    for p in products
                ],
                "count": len(products),
            }

        # ── Invoice routes ─────────────────────────────────────

        @router.post("/invoice/create")
        async def create_invoice(request: InvoiceRequest) -> dict[str, Any]:
            """Generate a GST invoice."""
            from .tools.invoicing import calculate_invoice
            invoice = calculate_invoice(
                items=request.items,
                business_name=request.business_name,
                contact_name=request.contact_name,
                gstin=request.gstin,
            )
            return invoice

        # ── Report routes ──────────────────────────────────────

        @router.post("/report/formatted-summary")
        async def formatted_summary() -> dict[str, str]:
            """Get formatted daily summary text."""
            from .tools.bookkeeping import get_daily_summary
            from .tools.reports import format_daily_summary
            summary = get_daily_summary()
            text = format_daily_summary({
                "date": summary.date,
                "total_sales": summary.total_sales,
                "total_purchases": summary.total_purchases,
                "total_payments_in": summary.total_payments_in,
                "total_payments_out": summary.total_payments_out,
                "total_expenses": summary.total_expenses,
                "net_position": summary.net_position,
                "transaction_count": summary.transaction_count,
                "top_credit_customers": summary.top_credit_customers,
                "total_outstanding": summary.total_outstanding,
            })
            return {"text": text}

        self._router = router
        return router

    def on_startup(self) -> None:
        """Vyapaar Sahayak startup hook."""
        logger.info("Vyapaar Sahayak plugin starting...")
        logger.info("Vyapaar Sahayak plugin started")

    def on_session_start(self, session: dict[str, Any]) -> dict[str, Any]:
        """Initialise Vyapaar-specific session state."""
        session.setdefault("app_state", {})
        session["app_state"].setdefault("business_name", "")
        session["app_state"].setdefault("last_contact", None)
        session["app_state"].setdefault("pending_confirmation", None)
        return session


def create_plugin() -> VyapaarPlugin:
    """Factory function called by PluginRegistry.discover_and_load()."""
    return VyapaarPlugin()


# --- Utility functions ---

def _txn_response(result) -> dict[str, Any]:
    """Format a TransactionResult for API response."""
    resp: dict[str, Any] = {
        "transaction_id": result.transaction.id,
        "type": result.transaction.type,
        "amount_paisa": result.transaction.amount,
        "amount_rupees": result.transaction.amount / 100,
        "payment_mode": result.transaction.payment_mode,
        "date": result.transaction.date,
    }
    if result.contact:
        resp["contact_name"] = result.contact.name
        resp["new_balance_paisa"] = result.new_balance
        resp["new_balance_rupees"] = result.new_balance / 100
    if result.alerts:
        resp["alerts"] = result.alerts
    return resp


def _strip_json_block(text: str) -> str:
    """Remove JSON blocks from text to get conversational part."""
    cleaned = re.sub(r'```json\s*\{[^`]*\}\s*```', '', text, flags=re.DOTALL)
    cleaned = re.sub(r'```\s*\{[^`]*\}\s*```', '', cleaned, flags=re.DOTALL)
    lines = cleaned.split('\n')
    non_json_lines = []
    in_json = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('{'):
            in_json = True
        if not in_json:
            non_json_lines.append(line)
        if in_json and stripped.endswith('}'):
            in_json = False
    return '\n'.join(non_json_lines).strip()


def _extract_json(text: str) -> dict[str, Any] | None:
    """Try to extract a JSON object from mixed text."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None
