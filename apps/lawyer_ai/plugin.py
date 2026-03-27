"""Lawyer AI plugin — implements BasePlugin for legal assistance."""

import json
import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from core.api.plugin_registry import BasePlugin
from core.llm.prompt_builder import build_system_prompt

from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# --- Pydantic models ---

class AskRequest(BaseModel):
    """Legal question request."""
    question: str
    user_id: str | None = None
    language: str = "hi"


# --- In-memory query store (MVP) ---

_query_store: list[dict[str, Any]] = []


# --- Plugin ---

class LawyerAIPlugin(BasePlugin):
    """Lawyer AI plugin for Indian legal assistance."""

    @property
    def app_id(self) -> str:
        return "lawyer_ai"

    def system_prompt(self, language: str, context: dict[str, Any]) -> str:
        """Return legal assistant system prompt."""
        return build_system_prompt(SYSTEM_PROMPT, language)

    def parse_response(self, llm_output: str, context: dict[str, Any]) -> dict[str, Any]:
        """Parse LLM JSON output into structured legal response."""
        logger.info("[LAWYER] Raw LLM output: %s", llm_output[:500])
        cleaned = _strip_markdown(llm_output)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = _extract_json(cleaned)
            if data is None:
                logger.warning("[LAWYER] Could not parse JSON, returning raw text")
                return {
                    "response_text": llm_output.strip(),
                    "answer": llm_output.strip(),
                }

        # Ensure response_text exists
        if not data.get("response_text"):
            data["response_text"] = data.get("answer", "")

        return data

    def router(self) -> APIRouter:
        """Return Lawyer AI specific routes."""
        router = APIRouter()

        @router.post("/ask")
        async def ask_legal_question(request: AskRequest) -> dict[str, Any]:
            """Ask a legal question (for direct API use, outside voice pipeline)."""
            # In production, this would call the LLM via pipeline.
            # For MVP, this is a stub endpoint that records the query.
            import uuid
            query = {
                "id": str(uuid.uuid4()),
                "user_id": request.user_id,
                "query_text": request.question,
                "language": request.language,
                "response_text": None,  # Would be filled by LLM
                "sections_cited": None,
                "severity": None,
            }
            _query_store.append(query)
            return {
                "message": "Query received. Use the /lawyer_ai/chat endpoint for AI responses.",
                "query": query,
            }

        @router.get("/queries")
        async def list_queries(user_id: str | None = None) -> dict[str, Any]:
            """List recorded queries."""
            if user_id:
                queries = [q for q in _query_store if q.get("user_id") == user_id]
            else:
                queries = _query_store
            return {"queries": queries, "count": len(queries)}

        return router

    def on_startup(self) -> None:
        logger.info("Lawyer AI plugin started")


def create_plugin() -> LawyerAIPlugin:
    """Factory function called by PluginRegistry.discover_and_load()."""
    return LawyerAIPlugin()


def _strip_markdown(text: str) -> str:
    """Strip markdown code fences from LLM output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return cleaned


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
