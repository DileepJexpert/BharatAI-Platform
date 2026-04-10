"""Agmarknet mandi price scraper — fetches commodity prices from markets.

Extends core/scraper/base.py BaseScraper. Runs every 2 hours.
In MVP, generates realistic sample data. In production, would
scrape agmarknet.gov.in or use their API.
"""

import logging
import random
from datetime import date
from typing import Any

from core.scraper.base import BaseScraper

logger = logging.getLogger(__name__)

COMMODITIES = [
    "Tomato", "Onion", "Potato", "Wheat", "Rice (Paddy)",
    "Soybean", "Mustard", "Chana (Gram)", "Moong", "Maize",
]

MARKETS = {
    "Madhya Pradesh": ["Indore", "Bhopal", "Dewas", "Ujjain", "Ratlam"],
    "Uttar Pradesh": ["Kanpur", "Lucknow", "Agra", "Varanasi", "Meerut"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Kota", "Udaipur", "Ajmer"],
}

# Base prices per quintal for realistic data generation
BASE_PRICES = {
    "Tomato": 2500, "Onion": 1800, "Potato": 1200, "Wheat": 2200,
    "Rice (Paddy)": 2100, "Soybean": 4500, "Mustard": 5200,
    "Chana (Gram)": 4800, "Moong": 7500, "Maize": 1900,
}


class AgmarknetScraper(BaseScraper):
    """Fetches daily mandi prices for commodities across markets."""

    @property
    def scraper_id(self) -> str:
        return "agmarknet_prices"

    @property
    def schedule_hours(self) -> float:
        return 2.0  # Every 2 hours

    async def scrape(self) -> dict:
        """Fetch/generate mandi price data.

        In production, this would hit agmarknet.gov.in.
        For MVP, generates realistic sample data.
        """
        records = []
        today = date.today().isoformat()

        for commodity in COMMODITIES:
            base = BASE_PRICES.get(commodity, 2000)
            for state_name, markets in MARKETS.items():
                for market in markets:
                    seed = hash(f"{commodity}:{market}:{today}")
                    random.seed(seed)
                    variation = random.uniform(0.85, 1.15)
                    modal = round(base * variation)

                    records.append({
                        "commodity": commodity,
                        "market": market,
                        "state": state_name,
                        "modal_price": modal,
                        "min_price": round(modal * 0.9),
                        "max_price": round(modal * 1.1),
                        "arrival_tonnes": round(random.uniform(50, 500), 1),
                        "price_date": today,
                        "unit": "Rs/quintal",
                    })

        # Store in the mandi_tools price store
        try:
            from apps.kisanmitra.tools.mandi_tools import store_prices
            stored = store_prices(records)
            logger.info("Stored %d price records", stored)
        except Exception as exc:
            logger.warning("Failed to store prices: %s", exc)

        logger.info(
            "Agmarknet scraper: %d commodities × %d markets = %d records",
            len(COMMODITIES),
            sum(len(m) for m in MARKETS.values()),
            len(records),
        )

        return {"records_added": len(records), "errors": []}
