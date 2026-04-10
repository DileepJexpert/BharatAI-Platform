"""Scraper scheduler — discovers and runs scrapers from plugins on schedule."""

import asyncio
import logging
import time
from typing import Any

from core.scraper.base import BaseScraper

logger = logging.getLogger(__name__)


class ScraperScheduler:
    """Discovers scrapers from registered plugins and runs them on schedule."""

    def __init__(self) -> None:
        self._scrapers: dict[str, BaseScraper] = {}
        self._task: asyncio.Task | None = None
        self._running = False

    def register(self, scraper: BaseScraper) -> None:
        """Register a scraper instance."""
        if not isinstance(scraper, BaseScraper):
            raise TypeError(f"{type(scraper).__name__} does not extend BaseScraper")
        self._scrapers[scraper.scraper_id] = scraper
        logger.info(
            "Scraper registered: %s (every %.1fh)",
            scraper.scraper_id,
            scraper.schedule_hours,
        )

    @property
    def scraper_ids(self) -> list[str]:
        return list(self._scrapers.keys())

    async def run_once(self, scraper_id: str) -> dict[str, Any]:
        """Run a specific scraper immediately."""
        scraper = self._scrapers.get(scraper_id)
        if scraper is None:
            return {"error": f"Unknown scraper: {scraper_id}"}

        start = time.time()
        try:
            result = await scraper.scrape()
            elapsed = time.time() - start
            logger.info(
                "Scraper %s completed in %.1fs: %s",
                scraper_id,
                elapsed,
                result,
            )
            return {"scraper_id": scraper_id, "elapsed_s": round(elapsed, 1), **result}
        except Exception as exc:
            logger.error("Scraper %s failed: %s", scraper_id, exc)
            return {"scraper_id": scraper_id, "error": str(exc)}

    async def start(self) -> None:
        """Start the scheduler loop in the background."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Scraper scheduler started with %d scrapers", len(self._scrapers))

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scraper scheduler stopped")

    async def _loop(self) -> None:
        """Main scheduler loop — checks each scraper against its schedule."""
        last_run: dict[str, float] = {}

        while self._running:
            now = time.time()
            for sid, scraper in self._scrapers.items():
                interval_s = scraper.schedule_hours * 3600
                last = last_run.get(sid, 0)

                if now - last >= interval_s:
                    try:
                        await scraper.scrape()
                        last_run[sid] = time.time()
                    except Exception as exc:
                        logger.error("Scraper %s failed: %s", sid, exc)

            await asyncio.sleep(60)  # Check every minute
