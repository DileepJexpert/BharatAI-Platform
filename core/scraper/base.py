"""BaseScraper ABC — all domain scrapers extend this."""

from abc import ABC, abstractmethod


class BaseScraper(ABC):
    """Abstract base for domain-specific scrapers.

    Subclasses define what to scrape and how often.
    The core scheduler discovers and runs them automatically.
    """

    @property
    @abstractmethod
    def scraper_id(self) -> str:
        """Unique identifier for this scraper (e.g., 'agmarknet_prices')."""

    @property
    @abstractmethod
    def schedule_hours(self) -> float:
        """Run interval in hours (e.g., 2.0 for every 2 hours, 24.0 for daily)."""

    @abstractmethod
    async def scrape(self) -> dict:
        """Execute the scrape operation.

        Returns a summary dict: {"records_added": int, "errors": list[str]}
        """

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.scraper_id} every={self.schedule_hours}h>"
