"""Tests for core/agents/ — AgentState, BaseSupervisor, intent classification."""

import pytest

from core.agents.state import AgentState
from core.agents.base_graph import AgentRegistration, BaseSupervisor


class TestAgentState:
    """Test the AgentState TypedDict."""

    def test_create_minimal_state(self):
        state: AgentState = {
            "user_id": "u1",
            "messages": [{"role": "user", "content": "hello"}],
        }
        assert state["user_id"] == "u1"

    def test_create_full_state(self):
        state: AgentState = {
            "user_id": "u1",
            "user_profile": {"name": "Ramu"},
            "messages": [],
            "current_agent": "scheme",
            "tools_used": ["search_schemes"],
            "agent_results": {"response": "Found 3 schemes"},
            "follow_up_actions": [{"action": "check_eligibility"}],
            "language": "hi",
            "error": None,
        }
        assert state["current_agent"] == "scheme"
        assert state["language"] == "hi"


class TestAgentRegistration:
    """Test the AgentRegistration class."""

    def test_create_registration(self):
        reg = AgentRegistration(
            name="scheme",
            builder=lambda: None,
            keywords=["yojana", "scheme"],
        )
        assert reg.name == "scheme"
        assert "yojana" in reg.keywords

    def test_default_keywords(self):
        reg = AgentRegistration(name="general", builder=lambda: None)
        assert reg.keywords == []


class TestBaseSupervisor:
    """Test the BaseSupervisor agent router."""

    def test_register_agent(self):
        sup = BaseSupervisor()
        sup.register_agent("scheme", lambda: None, ["yojana", "scheme"])
        assert "scheme" in sup.agent_names

    def test_register_multiple_agents(self):
        sup = BaseSupervisor()
        sup.register_agent("scheme", lambda: None, ["yojana"])
        sup.register_agent("mandi", lambda: None, ["price", "mandi"])
        assert len(sup.agent_names) == 2

    @pytest.mark.asyncio
    async def test_classify_intent_keyword_match(self):
        sup = BaseSupervisor()
        sup.register_agent("scheme", lambda: None, ["yojana", "scheme", "sarkari"])
        sup.register_agent("mandi", lambda: None, ["price", "mandi", "bhav"])

        agent, confidence = await sup.classify_intent("mandi bhav kya hai?")
        assert agent == "mandi"
        assert confidence > 0

    @pytest.mark.asyncio
    async def test_classify_intent_no_match(self):
        sup = BaseSupervisor()
        sup.register_agent("scheme", lambda: None, ["yojana"])

        agent, confidence = await sup.classify_intent("what is the weather?")
        assert agent == "general"
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_classify_intent_best_match(self):
        sup = BaseSupervisor()
        sup.register_agent("scheme", lambda: None, ["yojana", "scheme"])
        sup.register_agent("mandi", lambda: None, ["price", "mandi", "bhav"])

        # Message with more mandi keywords
        agent, _ = await sup.classify_intent("mandi mein price bhav")
        assert agent == "mandi"

    @pytest.mark.asyncio
    async def test_process_message_empty(self):
        sup = BaseSupervisor()
        result = await sup.process_message("u1", "")
        assert result["reply_text"]  # Should return prompt message
        assert result["agents_used"] == []

    @pytest.mark.asyncio
    async def test_process_message_empty_hindi(self):
        sup = BaseSupervisor()
        result = await sup.process_message("u1", "", language="hi")
        assert "सवाल" in result["reply_text"]

    @pytest.mark.asyncio
    async def test_process_message_general(self):
        sup = BaseSupervisor()
        result = await sup.process_message("u1", "hello there", language="en")
        assert "general" in result["agents_used"]
        assert "classification" in result

    @pytest.mark.asyncio
    async def test_process_message_with_agent(self):
        sup = BaseSupervisor()
        sup.register_agent("scheme", lambda: None, ["yojana", "scheme"])

        result = await sup.process_message("u1", "yojana bataiye")
        assert "scheme" in result["agents_used"]
        assert result["classification"]["agent"] == "scheme"
