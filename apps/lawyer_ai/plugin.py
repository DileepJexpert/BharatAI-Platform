"""Lawyer AI plugin — implements BasePlugin for legal assistance."""

import json
import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from core.api.plugin_registry import BasePlugin
from core.llm.prompt_builder import build_system_prompt

from .prompts import SYSTEM_PROMPT

logger = logging.getLogger("lawyer_ai")


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

        # The model now responds conversationally — just return the text
        # It may or may not include structured legal data
        response_text = llm_output.strip()

        # Try to extract any structured legal JSON if present
        data = _extract_json(llm_output)
        if data and (data.get("sections_cited") or data.get("severity")):
            logger.info("[LAWYER] Legal data found: sections=%s", data.get("sections_cited"))
            # Strip JSON from conversational text
            clean_text = _strip_json_block(llm_output).strip()
            data["response_text"] = clean_text or data.get("answer", response_text)
            return data

        logger.info("[LAWYER] Conversational response")
        return {"response_text": response_text}

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


def _strip_json_block(text: str) -> str:
    """Remove JSON blocks from text to get conversational part."""
    import re
    cleaned = re.sub(r'```json\s*\{[^`]*\}\s*```', '', text, flags=re.DOTALL)
    cleaned = re.sub(r'```\s*\{[^`]*\}\s*```', '', cleaned, flags=re.DOTALL)
    lines = cleaned.split('\n')
    non_json_lines = []
    in_json = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('{'):
            in_json = True
        if not in_json:
            non_json_lines.append(line)
        if in_json and stripped.endswith('}'):
            in_json = False
    return '\n'.join(non_json_lines).strip()


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
