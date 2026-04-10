"""BaseScheduledTask ABC — all domain background tasks extend this."""

from abc import ABC, abstractmethod


class BaseScheduledTask(ABC):
    """Abstract base for periodic background tasks.

    Subclasses define what to run and how often.
    The core TaskRunner discovers and runs them automatically.
    """

    @property
    @abstractmethod
    def task_id(self) -> str:
        """Unique identifier for this task (e.g., 'price_alert_check')."""

    @property
    @abstractmethod
    def interval_seconds(self) -> float:
        """Run interval in seconds (e.g., 3600 for hourly, 86400 for daily)."""

    @abstractmethod
    async def run(self) -> dict:
        """Execute the task.

        Returns a summary dict: {"processed": int, "errors": list[str]}
        """

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.task_id} every={self.interval_seconds}s>"
