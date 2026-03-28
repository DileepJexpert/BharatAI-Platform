"""Session store with Redis backend and in-memory fallback."""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("session")

SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "1800"))  # 30 min
MAX_CONVERSATION_TURNS: int = 5
SESSION_KEY_PREFIX: str = "bharatai:session:"


class SessionStore:
    """Session store: uses Redis when available, falls back to in-memory dict."""

    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client
        self._redis_available: bool | None = None  # None = not checked yet
        self._memory_store: dict[str, dict[str, Any]] = {}
        self._memory_expiry: dict[str, float] = {}  # session_id -> expiry timestamp

    async def _get_redis(self) -> Any:
        """Lazy init Redis client. Raises if Redis is not available."""
        if self._redis is None:
            import redis.asyncio as aioredis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self._redis = aioredis.from_url(redis_url, decode_responses=True)
        return self._redis

    async def _check_redis(self) -> bool:
        """Check if Redis is reachable. Caches the result."""
        if self._redis_available is not None:
            return self._redis_available
        try:
            r = await self._get_redis()
            await r.ping()
            self._redis_available = True
            logger.info("[SESSION] Redis connected — using Redis store")
        except Exception as exc:
            self._redis_available = False
            logger.warning("[SESSION] Redis not available (%s) — using in-memory store", exc)
        return self._redis_available

    def _key(self, session_id: str) -> str:
        """Build the Redis key for a session."""
        return f"{SESSION_KEY_PREFIX}{session_id}"

    def _cleanup_expired(self) -> None:
        """Remove expired sessions from memory store."""
        now = time.time()
        expired = [sid for sid, exp in self._memory_expiry.items() if exp < now]
        for sid in expired:
            self._memory_store.pop(sid, None)
            self._memory_expiry.pop(sid, None)

    # --- Core operations ---

    async def get(self, session_id: str) -> dict[str, Any] | None:
        """Fetch a session by ID. Returns None if not found."""
        logger.info("[SESSION] Getting session: %s", session_id[:30])

        if await self._check_redis():
            try:
                redis = await self._get_redis()
                raw = await redis.get(self._key(session_id))
                if raw is None:
                    logger.info("[SESSION] Session not found (new user)")
                    return None
                data = json.loads(raw)
                await redis.expire(self._key(session_id), SESSION_TTL_SECONDS)
                data["last_active"] = datetime.now(timezone.utc).isoformat()
                turns = len(data.get("conversation_history", []))
                logger.info("[SESSION] Session loaded (Redis): app=%s, language=%s, history_turns=%d",
                            data.get("app_id"), data.get("language"), turns)
                return data
            except Exception as exc:
                logger.warning("[SESSION] Redis read failed (%s), falling back to memory", exc)
                self._redis_available = False

        # In-memory fallback
        self._cleanup_expired()
        data = self._memory_store.get(session_id)
        if data is None:
            logger.info("[SESSION] Session not found (new user)")
            return None

        # Refresh expiry
        self._memory_expiry[session_id] = time.time() + SESSION_TTL_SECONDS
        data["last_active"] = datetime.now(timezone.utc).isoformat()
        turns = len(data.get("conversation_history", []))
        logger.info("[SESSION] Session loaded (memory): app=%s, language=%s, history_turns=%d",
                    data.get("app_id"), data.get("language"), turns)
        return data

    async def save(self, session_id: str, data: dict[str, Any]) -> None:
        """Save session data. Trims conversation_history to MAX_CONVERSATION_TURNS pairs."""
        history = data.get("conversation_history", [])
        max_entries = MAX_CONVERSATION_TURNS * 2
        if len(history) > max_entries:
            data["conversation_history"] = history[-max_entries:]

        data["last_active"] = datetime.now(timezone.utc).isoformat()

        if await self._check_redis():
            try:
                redis = await self._get_redis()
                await redis.setex(
                    self._key(session_id),
                    SESSION_TTL_SECONDS,
                    json.dumps(data),
                )
                return
            except Exception as exc:
                logger.warning("[SESSION] Redis write failed (%s), falling back to memory", exc)
                self._redis_available = False

        # In-memory fallback
        self._memory_store[session_id] = data
        self._memory_expiry[session_id] = time.time() + SESSION_TTL_SECONDS

    async def delete(self, session_id: str) -> None:
        """Delete a session."""
        if await self._check_redis():
            try:
                redis = await self._get_redis()
                await redis.delete(self._key(session_id))
                return
            except Exception:
                self._redis_available = False

        self._memory_store.pop(session_id, None)
        self._memory_expiry.pop(session_id, None)

    async def create(
        self,
        session_id: str,
        app_id: str,
        worker_id: str | None = None,
        language: str = "hi",
    ) -> dict[str, Any]:
        """Create a new session with default schema."""
        logger.info("[SESSION] Creating new session: id=%s, app=%s, lang=%s", session_id[:30], app_id, language)
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
        """Add a conversation turn to an existing session."""
        data = await self.get(session_id)
        if data is None:
            return None

        data.setdefault("conversation_history", []).append({
            "role": role,
            "text": text,
        })

        turns = len(data["conversation_history"])
        logger.info("[SESSION] Added turn: role=%s, total_turns=%d (max=%d)", role, turns, MAX_CONVERSATION_TURNS * 2)
        if turns > MAX_CONVERSATION_TURNS * 2:
            logger.info("[SESSION] Trimming old turns to keep last %d", MAX_CONVERSATION_TURNS * 2)

        await self.save(session_id, data)
        return data

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None
        self._memory_store.clear()
        self._memory_expiry.clear()
