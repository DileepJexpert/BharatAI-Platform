"""Tests for core/voice/session_store.py — session CRUD, TTL, max turns."""

import json
import pytest
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis

from core.voice.session_store import SessionStore, MAX_CONVERSATION_TURNS


@pytest.fixture
async def redis_client():
    """Create a fakeredis async client."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def session_store(redis_client):
    """Session store backed by fakeredis."""
    store = SessionStore(redis_client=redis_client)
    yield store


class TestSessionCreate:
    """Test session creation."""

    @pytest.mark.asyncio
    async def test_create_session(self, session_store):
        session = await session_store.create(
            session_id="test-001",
            app_id="asha_health",
            worker_id="worker-001",
            language="hi",
        )
        assert session["session_id"] == "test-001"
        assert session["app_id"] == "asha_health"
        assert session["worker_id"] == "worker-001"
        assert session["language"] == "hi"
        assert session["conversation_history"] == []
        assert session["app_state"] == {}

    @pytest.mark.asyncio
    async def test_create_session_default_language(self, session_store):
        session = await session_store.create(
            session_id="test-002",
            app_id="asha_health",
        )
        assert session["language"] == "hi"


class TestSessionGetSaveDelete:
    """Test basic CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_existing_session(self, session_store):
        await session_store.create("test-get", "asha_health")
        session = await session_store.get("test-get")
        assert session is not None
        assert session["session_id"] == "test-get"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, session_store):
        session = await session_store.get("nonexistent")
        assert session is None

    @pytest.mark.asyncio
    async def test_delete_session(self, session_store):
        await session_store.create("test-del", "asha_health")
        await session_store.delete("test-del")
        session = await session_store.get("test-del")
        assert session is None

    @pytest.mark.asyncio
    async def test_save_updates_session(self, session_store):
        await session_store.create("test-update", "asha_health")
        session = await session_store.get("test-update")
        session["language"] = "mr"
        await session_store.save("test-update", session)

        updated = await session_store.get("test-update")
        assert updated["language"] == "mr"


class TestSessionTTL:
    """Test TTL behavior."""

    @pytest.mark.asyncio
    async def test_session_has_ttl(self, session_store, redis_client):
        await session_store.create("test-ttl", "asha_health")
        key = "bharatai:session:test-ttl"
        ttl = await redis_client.ttl(key)
        assert ttl > 0
        assert ttl <= 1800  # 30 minutes

    @pytest.mark.asyncio
    async def test_get_refreshes_ttl(self, session_store, redis_client):
        await session_store.create("test-ttl-refresh", "asha_health")
        key = "bharatai:session:test-ttl-refresh"

        # Manually reduce TTL
        await redis_client.expire(key, 100)
        ttl_before = await redis_client.ttl(key)
        assert ttl_before <= 100

        # Access refreshes TTL
        await session_store.get("test-ttl-refresh")
        ttl_after = await redis_client.ttl(key)
        assert ttl_after > ttl_before


class TestSessionConversationTurns:
    """Test max conversation turn trimming."""

    @pytest.mark.asyncio
    async def test_add_turn(self, session_store):
        await session_store.create("test-turn", "asha_health")
        await session_store.add_turn("test-turn", "user", "hello")
        await session_store.add_turn("test-turn", "assistant", "hi there")

        session = await session_store.get("test-turn")
        assert len(session["conversation_history"]) == 2
        assert session["conversation_history"][0]["role"] == "user"
        assert session["conversation_history"][1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_max_turns_trimmed(self, session_store):
        await session_store.create("test-trim", "asha_health")

        # Add more than MAX_CONVERSATION_TURNS * 2 entries
        for i in range(MAX_CONVERSATION_TURNS * 2 + 4):
            role = "user" if i % 2 == 0 else "assistant"
            await session_store.add_turn("test-trim", role, f"message {i}")

        session = await session_store.get("test-trim")
        max_entries = MAX_CONVERSATION_TURNS * 2
        assert len(session["conversation_history"]) <= max_entries

    @pytest.mark.asyncio
    async def test_add_turn_nonexistent_session(self, session_store):
        result = await session_store.add_turn("nonexistent", "user", "hello")
        assert result is None
