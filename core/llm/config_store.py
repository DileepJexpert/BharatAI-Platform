"""Persistent model configuration store — Redis (fast) + PostgreSQL (durable)."""

import json
import logging
import os

from core.llm.router import AppModelConfig, FallbackEntry

logger = logging.getLogger("llm.config_store")

DEFAULT_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "ollama")
DEFAULT_MODEL = os.getenv("DEFAULT_LLM_MODEL", os.getenv("DEFAULT_MODEL", "llama3.2:3b-instruct-q4_0"))
REDIS_CONFIG_PREFIX = "bharatai:llm_config:"


class ModelConfigStore:
    """Stores model configuration in Redis (fast) with in-memory fallback.

    PostgreSQL persistence is available when the DB is connected.
    """

    def __init__(self, redis_client=None, db_session_factory=None):
        self._redis = redis_client
        self._db_factory = db_session_factory
        self._memory_cache: dict[str, dict] = {}

    async def get_app_config(self, app_id: str) -> AppModelConfig | None:
        """Get config for an app. Tries Redis → memory → DB → None."""
        # Try Redis
        if self._redis:
            try:
                raw = await self._redis.get(f"{REDIS_CONFIG_PREFIX}{app_id}")
                if raw:
                    return AppModelConfig.from_dict(json.loads(raw))
            except Exception as e:
                logger.debug("Redis get failed for %s: %s", app_id, e)

        # Try memory cache
        if app_id in self._memory_cache:
            return AppModelConfig.from_dict(self._memory_cache[app_id])

        # Try PostgreSQL
        if self._db_factory:
            try:
                return await self._load_from_db(app_id)
            except Exception as e:
                logger.debug("DB load failed for %s: %s", app_id, e)

        return None

    async def set_app_config(self, app_id: str, config: AppModelConfig, updated_by: str = "admin") -> None:
        """Save config. Writes to Redis (immediate) + DB (persistent) + memory."""
        data = config.to_dict()

        # Always update memory cache
        self._memory_cache[app_id] = data

        # Write to Redis (immediate effect)
        if self._redis:
            try:
                await self._redis.set(
                    f"{REDIS_CONFIG_PREFIX}{app_id}",
                    json.dumps(data),
                )
            except Exception as e:
                logger.warning("Redis set failed for %s: %s", app_id, e)

        # Write to PostgreSQL (persistence)
        if self._db_factory:
            try:
                await self._save_to_db(app_id, data, updated_by)
            except Exception as e:
                logger.warning("DB save failed for %s: %s", app_id, e)

        logger.info("Config updated for %s: %s/%s (by %s)", app_id, config.provider, config.model, updated_by)

    async def get_all_configs(self) -> dict[str, AppModelConfig]:
        """Get configs for all apps. Used by admin dashboard."""
        result: dict[str, AppModelConfig] = {}

        # Start with memory cache
        for app_id, data in self._memory_cache.items():
            result[app_id] = AppModelConfig.from_dict(data)

        # Overlay DB configs
        if self._db_factory:
            try:
                db_configs = await self._load_all_from_db()
                for app_id, config in db_configs.items():
                    if app_id not in result:
                        result[app_id] = config
            except Exception as e:
                logger.debug("DB load all failed: %s", e)

        return result

    def get_default_config(self) -> AppModelConfig:
        """Build default config from environment variables."""
        return AppModelConfig(
            provider=DEFAULT_PROVIDER,
            model=DEFAULT_MODEL,
            temperature=float(os.getenv("DEFAULT_LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("DEFAULT_LLM_MAX_TOKENS", "2048")),
            fallback_chain=self._parse_fallback_chain(),
        )

    def _parse_fallback_chain(self) -> list[FallbackEntry]:
        """Parse DEFAULT_LLM_FALLBACK env: 'groq:llama-3.3-70b,ollama:qwen3:1.7b'."""
        raw = os.getenv("DEFAULT_LLM_FALLBACK", "")
        if not raw:
            return []
        entries = []
        for part in raw.split(","):
            part = part.strip()
            if ":" in part:
                provider, model = part.split(":", 1)
                entries.append(FallbackEntry(provider=provider, model=model))
        return entries

    async def delete_app_config(self, app_id: str) -> None:
        """Remove app-specific config, reverting to default."""
        self._memory_cache.pop(app_id, None)

        if self._redis:
            try:
                await self._redis.delete(f"{REDIS_CONFIG_PREFIX}{app_id}")
            except Exception:
                pass

        if self._db_factory:
            try:
                await self._delete_from_db(app_id)
            except Exception:
                pass

    async def load_all_to_router(self, router) -> None:
        """Load all stored configs into the router on startup."""
        configs = await self.get_all_configs()
        for app_id, config in configs.items():
            if app_id == "default":
                router.set_default_config(config)
            else:
                router.set_app_config(app_id, config)

    # --- PostgreSQL helpers ---

    async def _load_from_db(self, app_id: str) -> AppModelConfig | None:
        async with self._db_factory() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("SELECT provider, model, temperature, max_tokens, fallback_chain FROM model_configs WHERE app_id = :app_id"),
                {"app_id": app_id},
            )
            row = result.fetchone()
            if not row:
                return None
            chain_data = row[4] if row[4] else []
            return AppModelConfig(
                provider=row[0],
                model=row[1],
                temperature=row[2] or 0.7,
                max_tokens=row[3] or 2048,
                fallback_chain=[FallbackEntry(**f) for f in chain_data],
            )

    async def _load_all_from_db(self) -> dict[str, AppModelConfig]:
        result = {}
        async with self._db_factory() as session:
            from sqlalchemy import text
            rows = await session.execute(
                text("SELECT app_id, provider, model, temperature, max_tokens, fallback_chain FROM model_configs")
            )
            for row in rows.fetchall():
                chain_data = row[5] if row[5] else []
                result[row[0]] = AppModelConfig(
                    provider=row[1],
                    model=row[2],
                    temperature=row[3] or 0.7,
                    max_tokens=row[4] or 2048,
                    fallback_chain=[FallbackEntry(**f) for f in chain_data],
                )
        return result

    async def _save_to_db(self, app_id: str, data: dict, updated_by: str) -> None:
        async with self._db_factory() as session:
            from sqlalchemy import text
            await session.execute(
                text("""
                    INSERT INTO model_configs (app_id, provider, model, temperature, max_tokens, fallback_chain, updated_by, updated_at)
                    VALUES (:app_id, :provider, :model, :temperature, :max_tokens, :fallback_chain::jsonb, :updated_by, NOW())
                    ON CONFLICT (app_id)
                    DO UPDATE SET provider = :provider, model = :model, temperature = :temperature,
                                  max_tokens = :max_tokens, fallback_chain = :fallback_chain::jsonb,
                                  updated_by = :updated_by, updated_at = NOW()
                """),
                {
                    "app_id": app_id,
                    "provider": data["provider"],
                    "model": data["model"],
                    "temperature": data.get("temperature", 0.7),
                    "max_tokens": data.get("max_tokens", 2048),
                    "fallback_chain": json.dumps(data.get("fallback_chain", [])),
                    "updated_by": updated_by,
                },
            )
            await session.commit()

    async def _delete_from_db(self, app_id: str) -> None:
        async with self._db_factory() as session:
            from sqlalchemy import text
            await session.execute(
                text("DELETE FROM model_configs WHERE app_id = :app_id"),
                {"app_id": app_id},
            )
            await session.commit()
