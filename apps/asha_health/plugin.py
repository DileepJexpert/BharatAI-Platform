"""ASHA Health plugin — implements BasePlugin for voice-based health data entry."""

import json
import logging
import re
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.api.plugin_registry import BasePlugin
from core.llm.prompt_builder import build_system_prompt

from .nhm_client import NHMClient
from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# --- Pydantic models for ASHA routes ---

class VisitData(BaseModel):
    """Parsed visit data from LLM."""
    patient_name: str | None = None
    patient_age: int | None = None
    gender: str | None = None
    complaint: str | None = None
    temperature: float | None = None
    weight: float | None = None
    visit_date: str | None = None
    referral_needed: bool = False
    notes: str | None = None
    confirmation_message: str | None = None
    response_text: str | None = None


class ConfirmVisitRequest(BaseModel):
    """Request to confirm and save a visit."""
    visit_data: dict[str, Any]
    worker_id: str | None = None
    raw_transcript: str | None = None


# --- In-memory visit store (MVP — replaced with DB in production) ---

_visit_store: dict[str, list[dict[str, Any]]] = {}


def _get_visits_for_worker(worker_id: str) -> list[dict[str, Any]]:
    return _visit_store.get(worker_id, [])


def _save_visit(worker_id: str, visit: dict[str, Any]) -> dict[str, Any]:
    """Save visit to in-memory store. Returns visit with id and sync_status."""
    import uuid
    visit["id"] = str(uuid.uuid4())
    visit["sync_status"] = "pending"
    visit["worker_id"] = worker_id

    if worker_id not in _visit_store:
        _visit_store[worker_id] = []
    _visit_store[worker_id].append(visit)
    return visit


def _check_duplicate(worker_id: str, patient_name: str | None, visit_date: str | None) -> bool:
    """Check if a visit for the same worker+patient+date already exists."""
    if not patient_name or not worker_id:
        return False
    for visit in _get_visits_for_worker(worker_id):
        if (
            visit.get("patient_name") == patient_name
            and visit.get("visit_date") == visit_date
        ):
            return True
    return False


# --- Plugin ---

class AshaHealthPlugin(BasePlugin):
    """ASHA Health plugin for voice-based patient visit recording."""

    def __init__(self) -> None:
        self._nhm_client = NHMClient()
        self._router: APIRouter | None = None

    @property
    def app_id(self) -> str:
        return "asha_health"

    def system_prompt(self, language: str, context: dict[str, Any]) -> str:
        """Return ASHA system prompt formatted with the detected language."""
        return build_system_prompt(SYSTEM_PROMPT, language)

    def parse_response(self, llm_output: str, context: dict[str, Any]) -> dict[str, Any]:
        """Parse LLM JSON output into structured visit data.

        Handles:
        - Markdown-wrapped JSON (```json ... ```)
        - Temperature F→C conversion
        - Default visit_date to today
        - Sets response_text from confirmation_message
        """
        cleaned = _strip_markdown(llm_output)
        data = json.loads(cleaned)

        # Temperature F→C conversion if > 50 (likely Fahrenheit)
        temp = data.get("temperature")
        if temp is not None and temp > 50:
            data["temperature"] = round((temp - 32) * 5 / 9, 1)

        # Default visit_date to today
        if not data.get("visit_date"):
            data["visit_date"] = date.today().isoformat()

        # Ensure response_text exists
        if not data.get("response_text"):
            data["response_text"] = data.get("confirmation_message", "")

        return data

    def router(self) -> APIRouter:
        """Return ASHA-specific routes."""
        if self._router is not None:
            return self._router

        router = APIRouter()

        @router.get("/visits")
        async def list_visits(worker_id: str | None = None) -> dict[str, Any]:
            """List visits, optionally filtered by worker_id."""
            if worker_id:
                visits = _get_visits_for_worker(worker_id)
            else:
                visits = []
                for wid_visits in _visit_store.values():
                    visits.extend(wid_visits)
            return {"visits": visits, "count": len(visits)}

        @router.post("/confirm")
        async def confirm_visit(request: ConfirmVisitRequest) -> dict[str, Any]:
            """Confirm and save a parsed visit."""
            visit_data = request.visit_data
            worker_id = request.worker_id or "unknown"
            visit_date = visit_data.get("visit_date", date.today().isoformat())

            # Duplicate check
            is_dup = _check_duplicate(
                worker_id,
                visit_data.get("patient_name"),
                visit_date,
            )
            if is_dup:
                return {
                    "warning": "duplicate",
                    "message": (
                        f"A visit for {visit_data.get('patient_name')} "
                        f"on {visit_date} already exists. "
                        "Send again to confirm saving a second visit."
                    ),
                    "visit_data": visit_data,
                }

            # Save
            if request.raw_transcript:
                visit_data["raw_transcript"] = request.raw_transcript

            saved = _save_visit(worker_id, visit_data)

            # Queue for NHM sync (no-op in MVP)
            await self._nhm_client.sync_visit(saved)

            return {
                "message": "Visit saved",
                "visit": saved,
            }

        self._router = router
        return router

    def on_startup(self) -> None:
        """Called once on platform start."""
        logger.info("ASHA Health plugin started")

    def on_session_start(self, session: dict[str, Any]) -> dict[str, Any]:
        """Initialise ASHA-specific session state."""
        session.setdefault("app_state", {})
        session["app_state"]["pending_visit"] = None
        return session


def create_plugin() -> AshaHealthPlugin:
    """Factory function called by PluginRegistry.discover_and_load()."""
    return AshaHealthPlugin()


def _strip_markdown(text: str) -> str:
    """Strip markdown code fences from LLM output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return cleaned
