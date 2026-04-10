"""Shared agent state definition for LangGraph agents."""

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """State shared across all LangGraph agent nodes.

    Domain plugins extend this with their own keys via agent_results.
    """

    user_id: str
    user_profile: dict[str, Any]
    messages: list[dict[str, str]]
    current_agent: str
    tools_used: list[str]
    agent_results: dict[str, Any]
    follow_up_actions: list[dict[str, Any]]
    language: str
    error: str | None
