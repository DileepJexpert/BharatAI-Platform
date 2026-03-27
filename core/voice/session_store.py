"""Redis-backed session store for voice pipeline conversations."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "1800"))  # 30 min
MAX_CONVERSATION_TURNS: int = 5
SESSION_KEY_PREFIX: str = "bharatai:session:"


class SessionStore:
    """Redis-backed session store with TTL and turn trimming."""

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self._redis = redis_client

    async def _get_redis(self) -> aioredis.Redis:
        """Lazy init Redis client."""
        if self._redis is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self._redis = aioredis.from_url(redis_url, decode_responses=True)
        return self._redis

    def _key(self, session_id: str) -> str:
        """Build the Redis key for a session."""
        return f"{SESSION_KEY_PREFIX}{session_id}"

    async def get(self, session_id: str) -> dict[str, Any] | None:
        """Fetch a session by ID. Returns None if not found.

        Refreshes TTL on access.
        """
        redis = await self._get_redis()
        raw = await redis.get(self._key(session_id))
        if raw is None:
            return None

        data = json.loads(raw)
        # Refresh TTL on access
        await redis.expire(self._key(session_id), SESSION_TTL_SECONDS)
        data["last_active"] = datetime.now(timezone.utc).isoformat()
        return data

    async def save(self, session_id: str, data: dict[str, Any]) -> None:
        """Save session data with TTL.

        Trims conversation_history to MAX_CONVERSATION_TURNS pairs.
        """
        # Trim conversation history
        history = data.get("conversation_history", [])
        max_entries = MAX_CONVERSATION_TURNS * 2  # user + assistant per turn
        if len(history) > max_entries:
            data["conversation_history"] = history[-max_entries:]

        data["last_active"] = datetime.now(timezone.utc).isoformat()

        redis = await self._get_redis()
        await redis.setex(
            self._key(session_id),
            SESSION_TTL_SECONDS,
            json.dumps(data),
        )

    async def delete(self, session_id: str) -> None:
        """Delete a session."""
        redis = await self._get_redis()
        await redis.delete(self._key(session_id))

    async def create(
        self,
        session_id: str,
        app_id: str,
        worker_id: str | None = None,
        language: str = "hi",
    ) -> dict[str, Any]:
        """Create a new session with default schema."""
        now = datetime.now(timezone.utc).isoformat()
        session = {
            "session_id": session_id,
            "app_id": app_id,
            "worker_id": worker_id,
            "language": language,
            "conversation_history": [],
            "app_state": {},
            "created_at": now,
            "last_active": now,
        }
        await self.save(session_id, session)
        return session

    async def add_turn(
        self,
        session_id: str,
        role: str,
        text: str,
    ) -> dict[str, Any] | None:
        """Add a conversation turn to an existing session.

        Args:
            session_id: session to update.
            role: 'user' or 'assistant'.
            text: the message text.

        Returns:
            Updated session data, or None if session not found.
        """
        data = await self.get(session_id)
        if data is None:
            return None

        data.setdefault("conversation_history", []).append({
            "role": role,
            "text": text,
        })

        await self.save(session_id, data)
        return data

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
