"""Tests for KisanMitra scrapers — AgmarknetScraper and SchemeScraper."""

import pytest

from apps.kisanmitra.scrapers.agmarknet_scraper import AgmarknetScraper
from apps.kisanmitra.scrapers.scheme_scraper import SchemeScraper
from core.scraper.base import BaseScraper


class TestAgmarknetScraper:
    """Test the mandi price scraper."""

    def test_is_base_scraper(self):
        scraper = AgmarknetScraper()
        assert isinstance(scraper, BaseScraper)

    def test_scraper_id(self):
        scraper = AgmarknetScraper()
        assert scraper.scraper_id == "agmarknet_prices"

    def test_schedule_hours(self):
        scraper = AgmarknetScraper()
        assert scraper.schedule_hours == 2.0

    @pytest.mark.asyncio
    async def test_scrape_returns_records(self):
        scraper = AgmarknetScraper()
        result = await scraper.scrape()
        assert "records_added" in result
        assert result["records_added"] > 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_scrape_produces_reasonable_count(self):
        scraper = AgmarknetScraper()
        result = await scraper.scrape()
        # 10 commodities × 15 markets = 150 records
        assert result["records_added"] == 150


class TestSchemeScraper:
    """Test the government scheme scraper."""

    def test_is_base_scraper(self):
        scraper = SchemeScraper()
        assert isinstance(scraper, BaseScraper)

    def test_scraper_id(self):
        scraper = SchemeScraper()
        assert scraper.scraper_id == "scheme_data"

    def test_schedule_hours(self):
        scraper = SchemeScraper()
        assert scraper.schedule_hours == 24.0

    @pytest.mark.asyncio
    async def test_scrape_returns_records(self):
        scraper = SchemeScraper()
        result = await scraper.scrape()
        assert "records_added" in result
        assert result["records_added"] > 0
