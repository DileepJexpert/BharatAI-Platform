"""Base LangGraph supervisor — generic multi-agent orchestration.

Domain plugins register their own agent nodes. The supervisor:
1. Classifies user intent via keyword matching + LLM fallback
2. Routes to the appropriate domain sub-agent
3. Saves conversation context
4. Builds the final response

Usage from a plugin:
    from core.agents.base_graph import BaseSupervisor

    supervisor = BaseSupervisor(llm_client=ollama_client)
    supervisor.register_agent("scheme", build_scheme_agent, keywords=["yojana", ...])
    result = await supervisor.process_message(user_id, message, language="hi")
"""

import logging
import time
from typing import Any, Callable

from core.agents.state import AgentState

logger = logging.getLogger(__name__)

# Optional: only import langgraph if available
try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.info("langgraph not installed — agent framework will use simple routing")


class AgentRegistration:
    """Metadata for a registered domain agent."""

    def __init__(
        self,
        name: str,
        builder: Callable,
        keywords: list[str] | None = None,
    ) -> None:
        self.name = name
        self.builder = builder
        self.keywords = keywords or []


class BaseSupervisor:
    """Generic supervisor that routes messages to domain sub-agents.

    Works with or without LangGraph installed:
    - With LangGraph: uses StateGraph for orchestration
    - Without LangGraph: uses simple keyword + LLM classification
    """

    def __init__(self, llm_client: Any = None) -> None:
        self._agents: dict[str, AgentRegistration] = {}
        self._llm_client = llm_client

    def register_agent(
        self,
        name: str,
        builder: Callable,
        keywords: list[str] | None = None,
    ) -> None:
        """Register a domain sub-agent."""
        self._agents[name] = AgentRegistration(name, builder, keywords)
        logger.info("Agent registered: %s (%d keywords)", name, len(keywords or []))

    @property
    def agent_names(self) -> list[str]:
        return list(self._agents.keys())

    async def classify_intent(self, message: str) -> tuple[str, float]:
        """Classify user message intent using keyword matching.

        Returns (agent_name, confidence). Falls back to "general" if no match.
        """
        lower = message.lower()
        scores: dict[str, int] = {}

        for name, reg in self._agents.items():
            score = sum(1 for kw in reg.keywords if kw in lower)
            if score > 0:
                scores[name] = score

        if scores:
            best = max(scores, key=scores.get)  # type: ignore[arg-type]
            confidence = scores[best] / max(len(self._agents[best].keywords), 1)
            if confidence >= 0.05:  # At least one keyword match
                return best, round(min(confidence, 1.0), 2)

        return "general", 0.0

    async def process_message(
        self,
        user_id: str,
        message: str,
        language: str = "hi",
        user_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process a message through intent classification and agent routing.

        Returns a dict with: reply_text, agents_used, actions_taken, follow_up_actions.
        """
        start = time.time()

        if not message.strip():
            return {
                "reply_text": "Please type or speak your question."
                if language != "hi"
                else "कृपया अपना सवाल लिखें या बोलें।",
                "agents_used": [],
                "actions_taken": [],
                "follow_up_actions": [],
            }

        # Classify intent
        agent_name, confidence = await self.classify_intent(message)

        state: AgentState = {
            "user_id": user_id,
            "messages": [{"role": "user", "content": message}],
            "language": language,
            "user_profile": user_profile or {},
            "tools_used": [],
            "agent_results": {
                "classification": {
                    "agent": agent_name,
                    "confidence": confidence,
                }
            },
            "follow_up_actions": [],
            "current_agent": agent_name,
        }

        # Run sub-agent if registered and LangGraph available
        if agent_name != "general" and agent_name in self._agents:
            reg = self._agents[agent_name]
            if LANGGRAPH_AVAILABLE:
                try:
                    graph = reg.builder()
                    compiled = graph.compile()
                    result = await compiled.ainvoke(state)
                    if isinstance(result, dict):
                        state["agent_results"] = result.get(
                            "agent_results", state.get("agent_results", {})
                        )
                        state["tools_used"] = result.get(
                            "tools_used", state.get("tools_used", [])
                        )
                        state["follow_up_actions"] = result.get(
                            "follow_up_actions", state.get("follow_up_actions", [])
                        )
                except Exception as e:
                    logger.error("Agent %s failed: %s", agent_name, e)
                    state["error"] = str(e)

        reply_text = (
            state.get("agent_results", {}).get("final_response")
            or state.get("agent_results", {}).get("response", "")
        )

        latency_ms = int((time.time() - start) * 1000)
        logger.info(
            "Processed message: agent=%s, latency=%dms",
            agent_name,
            latency_ms,
        )

        return {
            "reply_text": reply_text,
            "agents_used": [agent_name],
            "actions_taken": state.get("tools_used", []),
            "follow_up_actions": state.get("follow_up_actions", []),
            "classification": state.get("agent_results", {}).get("classification", {}),
        }
