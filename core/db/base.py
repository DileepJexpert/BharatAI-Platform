"""SQLAlchemy async engine factory, session maker, and declarative Base."""

import os
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""
    pass


def get_database_url() -> str:
    """Read database URL from environment."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return url


def create_engine(database_url: str | None = None, echo: bool = False) -> AsyncEngine:
    """Create an async SQLAlchemy engine."""
    url = database_url or get_database_url()
    return create_async_engine(
        url,
        echo=echo,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# Module-level singletons — initialised lazily via init_db()
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db(database_url: str | None = None) -> None:
    """Initialise the module-level engine and session factory."""
    global _engine, _session_factory
    echo = os.getenv("DATABASE_ECHO", "false").lower() == "true"
    _engine = create_engine(database_url, echo=echo)
    _session_factory = create_session_factory(_engine)
    logger.info("Database engine initialised")


async def close_db() -> None:
    """Dispose the engine and release connections."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine closed")


def get_engine() -> AsyncEngine:
    """Return the module-level engine. Raises if not initialised."""
    if _engine is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the module-level session factory. Raises if not initialised."""
    if _session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
