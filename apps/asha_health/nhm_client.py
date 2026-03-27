"""NHM API sync client — offline-first queue for visit data.

MVP: saves visits locally with sync_status='pending'.
The sync method is a no-op stub. Real NHM API integration in Phase 5.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class NHMSyncError(Exception):
    """Raised when NHM sync fails."""
    pass


class NHMClient:
    """Offline-first NHM sync queue.

    Visits are saved locally with sync_status='pending'.
    When connectivity is available, sync() pushes pending visits to NHM.
    """

    def __init__(self) -> None:
        self._is_available = False

    @property
    def is_available(self) -> bool:
        """Check if NHM API is reachable. Always False for MVP."""
        return self._is_available

    async def sync_visit(self, visit_data: dict[str, Any]) -> dict[str, Any]:
        """Attempt to sync a single visit to NHM API.

        MVP: no-op that returns the visit with sync_status unchanged.
        The visit remains 'pending' in the local DB.

        Args:
            visit_data: visit record dict.

        Returns:
            visit_data with sync_status (unchanged for MVP).
        """
        if not self._is_available:
            logger.info(
                "NHM API unavailable — visit '%s' queued locally (sync_status=pending)",
                visit_data.get("id", "unknown"),
            )
            return visit_data

        # Post-MVP: real NHM API call here
        # try:
        #     response = await httpx_client.post(NHM_API_URL, json=visit_data)
        #     visit_data["sync_status"] = "synced"
        # except Exception:
        #     visit_data["sync_status"] = "failed"

        return visit_data

    async def sync_all_pending(self, pending_visits: list[dict[str, Any]]) -> dict[str, int]:
        """Attempt to sync all pending visits.

        MVP: no-op, returns counts showing all remain pending.

        Args:
            pending_visits: list of visit dicts with sync_status='pending'.

        Returns:
            Dict with synced/failed/pending counts.
        """
        results = {"synced": 0, "failed": 0, "pending": len(pending_visits)}

        if not self._is_available:
            logger.info(
                "NHM API unavailable — %d visits remain pending", len(pending_visits)
            )
            return results

        # Post-MVP: iterate and sync each
        return results
