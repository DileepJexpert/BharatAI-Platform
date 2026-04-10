"""Tests for core/scraper/ — BaseScraper ABC and ScraperScheduler."""

import asyncio
import pytest

from core.scraper.base import BaseScraper
from core.scraper.scheduler import ScraperScheduler


class MockScraper(BaseScraper):
    """Test scraper implementation."""

    def __init__(self, sid: str = "test_scraper", hours: float = 1.0):
        self._id = sid
        self._hours = hours
        self.call_count = 0

    @property
    def scraper_id(self) -> str:
        return self._id

    @property
    def schedule_hours(self) -> float:
        return self._hours

    async def scrape(self) -> dict:
        self.call_count += 1
        return {"records_added": 10, "errors": []}


class FailingScraper(BaseScraper):
    """Scraper that always fails."""

    @property
    def scraper_id(self) -> str:
        return "failing_scraper"

    @property
    def schedule_hours(self) -> float:
        return 1.0

    async def scrape(self) -> dict:
        raise RuntimeError("Scrape failed")


class TestBaseScraper:
    """Test the BaseScraper ABC."""

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseScraper()

    def test_concrete_implementation(self):
        scraper = MockScraper()
        assert scraper.scraper_id == "test_scraper"
        assert scraper.schedule_hours == 1.0

    def test_repr(self):
        scraper = MockScraper("my_scraper", 2.0)
        assert "my_scraper" in repr(scraper)
        assert "2.0h" in repr(scraper)

    @pytest.mark.asyncio
    async def test_scrape_returns_dict(self):
        scraper = MockScraper()
        result = await scraper.scrape()
        assert result["records_added"] == 10
        assert result["errors"] == []


class TestScraperScheduler:
    """Test the ScraperScheduler."""

    def test_register_scraper(self):
        scheduler = ScraperScheduler()
        scraper = MockScraper()
        scheduler.register(scraper)
        assert "test_scraper" in scheduler.scraper_ids

    def test_register_invalid_type(self):
        scheduler = ScraperScheduler()
        with pytest.raises(TypeError):
            scheduler.register("not a scraper")

    def test_register_multiple_scrapers(self):
        scheduler = ScraperScheduler()
        scheduler.register(MockScraper("s1"))
        scheduler.register(MockScraper("s2"))
        assert len(scheduler.scraper_ids) == 2

    @pytest.mark.asyncio
    async def test_run_once_success(self):
        scheduler = ScraperScheduler()
        scraper = MockScraper()
        scheduler.register(scraper)

        result = await scheduler.run_once("test_scraper")
        assert result["scraper_id"] == "test_scraper"
        assert result["records_added"] == 10
        assert "elapsed_s" in result
        assert scraper.call_count == 1

    @pytest.mark.asyncio
    async def test_run_once_unknown_scraper(self):
        scheduler = ScraperScheduler()
        result = await scheduler.run_once("nonexistent")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_run_once_failing_scraper(self):
        scheduler = ScraperScheduler()
        scheduler.register(FailingScraper())

        result = await scheduler.run_once("failing_scraper")
        assert result["scraper_id"] == "failing_scraper"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_start_stop(self):
        scheduler = ScraperScheduler()
        scheduler.register(MockScraper())

        await scheduler.start()
        assert scheduler._running is True
        assert scheduler._task is not None

        await scheduler.stop()
        assert scheduler._running is False
        assert scheduler._task is None

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        scheduler = ScraperScheduler()
        scheduler.register(MockScraper())

        await scheduler.start()
        task1 = scheduler._task
        await scheduler.start()  # Should not create new task
        assert scheduler._task is task1

        await scheduler.stop()
