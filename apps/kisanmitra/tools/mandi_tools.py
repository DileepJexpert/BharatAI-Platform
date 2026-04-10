"""Mandi tools — commodity price lookup, comparison, and prediction.

Uses in-memory price store populated by the AgmarknetScraper.
Falls back to sample data when no scraper data is available.
"""

import logging
import random
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Hindi to English commodity mapping
HINDI_COMMODITY_MAP: dict[str, str] = {
    "tamatar": "Tomato", "टमाटर": "Tomato",
    "pyaz": "Onion", "प्याज": "Onion",
    "aloo": "Potato", "आलू": "Potato",
    "gehun": "Wheat", "गेहूं": "Wheat",
    "dhan": "Rice (Paddy)", "धान": "Rice (Paddy)",
    "soybean": "Soybean", "सोयाबीन": "Soybean",
    "sarson": "Mustard", "सरसों": "Mustard",
    "chana": "Chana (Gram)", "चना": "Chana (Gram)",
    "moong": "Moong", "मूंग": "Moong",
    "makka": "Maize", "मक्का": "Maize",
    "tomato": "Tomato", "onion": "Onion", "potato": "Potato",
    "wheat": "Wheat", "rice": "Rice (Paddy)", "mustard": "Mustard",
    "maize": "Maize",
}

# Sample markets
MARKETS = [
    "Indore", "Bhopal", "Dewas", "Ujjain", "Ratlam",
    "Kanpur", "Lucknow", "Agra", "Varanasi", "Jaipur",
    "Ahmedabad", "Nagpur", "Pune", "Delhi", "Hyderabad",
]

# In-memory price store — populated by scraper, seeded with sample data
_price_store: dict[str, dict[str, list[dict[str, Any]]]] = {}


def normalize_commodity(name: str) -> str:
    """Convert Hindi/English commodity name to standard English name."""
    return HINDI_COMMODITY_MAP.get(name.lower().strip(), name.title())


def _get_sample_price(commodity: str, market: str) -> dict[str, Any]:
    """Generate sample price data for demo/testing."""
    # Deterministic seed from commodity+market for consistency
    seed = hash(f"{commodity}:{market}") % 10000
    random.seed(seed)
    base_prices = {
        "Tomato": 2500, "Onion": 1800, "Potato": 1200, "Wheat": 2200,
        "Rice (Paddy)": 2100, "Soybean": 4500, "Mustard": 5200,
        "Chana (Gram)": 4800, "Moong": 7500, "Maize": 1900,
    }
    base = base_prices.get(commodity, 2000)
    variation = random.uniform(0.85, 1.15)
    modal = round(base * variation)
    return {
        "commodity": commodity,
        "market": market,
        "modal_price": modal,
        "min_price": round(modal * 0.9),
        "max_price": round(modal * 1.1),
        "arrival_tonnes": round(random.uniform(50, 500), 1),
        "price_date": date.today().isoformat(),
        "unit": "Rs/quintal",
    }


def store_prices(prices: list[dict[str, Any]]) -> int:
    """Store scraped prices in the in-memory price store."""
    count = 0
    for p in prices:
        commodity = p.get("commodity", "")
        market = p.get("market", "")
        if not commodity or not market:
            continue
        _price_store.setdefault(commodity, {}).setdefault(market, [])
        _price_store[commodity][market].append(p)
        count += 1
    return count


async def get_price(commodity: str, market: str) -> dict[str, Any] | None:
    """Get the latest price for a commodity in a market."""
    # Check in-memory store first
    market_data = _price_store.get(commodity, {}).get(market, [])
    if market_data:
        return market_data[-1]

    # Fallback to sample data
    return _get_sample_price(commodity, market)


async def get_price_history(
    commodity: str, market: str, days: int = 30,
) -> list[dict[str, Any]]:
    """Get price history for last N days."""
    # Check store
    market_data = _price_store.get(commodity, {}).get(market, [])
    if market_data:
        return market_data[-days:]

    # Generate sample history
    history = []
    base = _get_sample_price(commodity, market)["modal_price"]
    for i in range(days):
        d = date.today() - timedelta(days=days - 1 - i)
        random.seed(hash(f"{commodity}:{market}:{d.isoformat()}"))
        variation = random.uniform(0.95, 1.05)
        modal = round(base * variation)
        history.append({
            "commodity": commodity,
            "market": market,
            "modal_price": modal,
            "min_price": round(modal * 0.9),
            "max_price": round(modal * 1.1),
            "price_date": d.isoformat(),
        })
    return history


async def compare_markets(
    commodity: str, max_markets: int = 5,
) -> list[dict[str, Any]]:
    """Compare prices across markets for a commodity."""
    results = []
    for market in MARKETS[:max_markets]:
        price = await get_price(commodity, market)
        if price:
            results.append(price)

    results.sort(key=lambda x: x.get("modal_price", 0), reverse=True)
    return results


async def predict_commodity_price(
    commodity: str, market: str, horizon_days: int = 7,
) -> dict[str, Any]:
    """Predict future price using core ML predictor."""
    history = await get_price_history(commodity, market, days=30)
    if len(history) < 3:
        return {"error": "Insufficient price history for prediction"}

    dates = [h["price_date"] for h in history]
    values = [float(h["modal_price"]) for h in history]

    try:
        from core.ml.predictor import TimeSeriesPredictor
        predictor = TimeSeriesPredictor()
        result = predictor.predict(dates, values, horizon_days)
        if result:
            current = values[-1]
            predicted = result.predicted_value
            change_pct = ((predicted - current) / current) * 100

            if change_pct > 5:
                recommendation = "Hold — prices likely to rise"
            elif change_pct < -5:
                recommendation = "Consider selling — prices may drop"
            else:
                recommendation = "Prices stable — sell at your convenience"

            return {
                "current_price": current,
                "predicted_price": predicted,
                "confidence_lower": result.confidence_lower,
                "confidence_upper": result.confidence_upper,
                "change_pct": round(change_pct, 1),
                "method": result.method,
                "recommendation": recommendation,
                "horizon_days": horizon_days,
            }
    except Exception as exc:
        logger.warning("Price prediction failed: %s", exc)

    return {"error": "Prediction unavailable"}
