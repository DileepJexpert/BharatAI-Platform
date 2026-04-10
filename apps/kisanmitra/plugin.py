"""KisanMitra plugin — implements BasePlugin for farmer/MSME assistance.

Provides:
- Government scheme discovery and eligibility checking
- Mandi price lookup, comparison, and prediction
- Loan advisory with EMI calculation
- Hindi/English bilingual support
- Registers scrapers for mandi prices and scheme data

Uses core/ frameworks:
- BaseSupervisor for multi-agent intent routing
- ChromaClient for scheme RAG search
- ScraperScheduler for periodic data updates
- TimeSeriesPredictor for price forecasting
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

logger = logging.getLogger("kisanmitra")


# --- Pydantic models ---

class SchemeSearchRequest(BaseModel):
    query: str
    sector: str | None = None
    state: str | None = None
    language: str = "hi"


class MandiPriceRequest(BaseModel):
    commodity: str
    market: str | None = None
    language: str = "hi"


class LoanQueryRequest(BaseModel):
    amount: float | None = None
    loan_type: str | None = None
    language: str = "hi"


class EMIRequest(BaseModel):
    principal: float
    annual_rate: float
    tenure_years: int


# --- Plugin ---

class KisanMitraPlugin(BasePlugin):
    """KisanMitra plugin for farmer and MSME assistance."""

    def __init__(self) -> None:
        self._router: APIRouter | None = None

    @property
    def app_id(self) -> str:
        return "kisanmitra"

    def system_prompt(self, language: str, context: dict[str, Any]) -> str:
        """Return KisanMitra system prompt formatted with language."""
        user_profile = context.get("user_profile", {})
        name = user_profile.get("name", "")
        return build_system_prompt(
            SYSTEM_PROMPT,
            language,
            extra_context={"user_name": name},
        )

    def parse_response(self, llm_output: str, context: dict[str, Any]) -> dict[str, Any]:
        """Parse LLM output — handles conversational text and structured data."""
        logger.info("[KM] Raw LLM output: %s", llm_output[:500])

        data = _extract_json(llm_output)
        if data and any(k in data for k in ("schemes", "price", "loan", "action")):
            logger.info("[KM] Structured data found: %s", list(data.keys()))
            clean_text = _strip_json_block(llm_output).strip()
            data["response_text"] = clean_text or data.get("response", llm_output.strip())
            return data

        logger.info("[KM] Conversational response")
        return {"response_text": llm_output.strip()}

    def router(self) -> APIRouter:
        """Return KisanMitra-specific routes."""
        if self._router is not None:
            return self._router

        router = APIRouter()

        @router.get("/help")
        async def help_text(language: str = "hi") -> dict[str, str]:
            """Return help text listing KisanMitra capabilities."""
            text = HELP_TEXT_HI if language == "hi" else HELP_TEXT_EN
            return {"help": text, "language": language}

        @router.post("/schemes/search")
        async def search_schemes(request: SchemeSearchRequest) -> dict[str, Any]:
            """Search government schemes via RAG."""
            from .tools.scheme_tools import search_schemes_rag
            results = await search_schemes_rag(
                query=request.query,
                app_id="kisanmitra",
                sector=request.sector,
                state=request.state,
            )
            return {"schemes": results, "count": len(results)}

        @router.post("/mandi/price")
        async def get_mandi_price(request: MandiPriceRequest) -> dict[str, Any]:
            """Get current mandi price for a commodity."""
            from .tools.mandi_tools import get_price, normalize_commodity
            commodity = normalize_commodity(request.commodity)
            market = request.market or "Indore"
            price = await get_price(commodity, market)
            if price:
                return {"commodity": commodity, "market": market, **price}
            return {
                "commodity": commodity,
                "market": market,
                "error": "Price data not available",
            }

        @router.post("/mandi/compare")
        async def compare_markets(request: MandiPriceRequest) -> dict[str, Any]:
            """Compare commodity prices across markets."""
            from .tools.mandi_tools import compare_markets, normalize_commodity
            commodity = normalize_commodity(request.commodity)
            results = await compare_markets(commodity)
            return {"commodity": commodity, "markets": results}

        @router.post("/mandi/predict")
        async def predict_price(request: MandiPriceRequest) -> dict[str, Any]:
            """Predict future price for a commodity."""
            from .tools.mandi_tools import predict_commodity_price, normalize_commodity
            commodity = normalize_commodity(request.commodity)
            market = request.market or "Indore"
            prediction = await predict_commodity_price(commodity, market)
            return {"commodity": commodity, "market": market, **prediction}

        @router.post("/loan/emi")
        async def calculate_emi(request: EMIRequest) -> dict[str, Any]:
            """Calculate EMI for given loan parameters."""
            from .tools.loan_tools import calculate_emi as calc
            return calc(request.principal, request.annual_rate, request.tenure_years)

        @router.post("/loan/eligibility")
        async def check_loan_eligibility(
            request: LoanQueryRequest,
        ) -> dict[str, Any]:
            """Check loan eligibility based on user profile."""
            from .tools.loan_tools import get_eligible_loans
            results = get_eligible_loans(
                loan_type=request.loan_type,
                amount_needed=request.amount,
            )
            return {"loans": results, "count": len(results)}

        self._router = router
        return router

    def on_startup(self) -> None:
        """Register KisanMitra scrapers and agents on platform start."""
        logger.info("KisanMitra plugin starting...")

        # Register scrapers with the core scheduler
        try:
            from core.scraper.scheduler import ScraperScheduler
            from .scrapers.agmarknet_scraper import AgmarknetScraper
            from .scrapers.scheme_scraper import SchemeScraper

            # These will be picked up by the gateway's scraper_scheduler
            # if the gateway passes the scheduler to plugins in future.
            # For now, just log availability.
            logger.info("[KM] Scrapers available: agmarknet_prices, scheme_data")
        except ImportError as exc:
            logger.info("[KM] Scraper registration skipped: %s", exc)

        logger.info("KisanMitra plugin started")

    def on_session_start(self, session: dict[str, Any]) -> dict[str, Any]:
        """Initialise KisanMitra-specific session state."""
        session.setdefault("app_state", {})
        session["app_state"].setdefault("last_commodity", None)
        session["app_state"].setdefault("last_market", None)
        session["app_state"].setdefault("user_profile", {})
        return session


def create_plugin() -> KisanMitraPlugin:
    """Factory function called by PluginRegistry.discover_and_load()."""
    return KisanMitraPlugin()


# --- Utility functions ---

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
