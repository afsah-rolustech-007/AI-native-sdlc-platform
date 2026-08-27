"""Async SQLAlchemy engine and session factory.

Call `make_async_engine` / `make_session_factory` with an explicit URL in tests.
Application code uses `get_engine()` which reads `Settings.database_url`.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from common.config import get_settings

_engine: AsyncEngine | None = None


def ensure_asyncpg_url(url: str) -> str:
    """Force the SQLAlchemy asyncpg driver regardless of how the URL was built."""
    _scheme, sep, rest = url.partition("://")
    if not sep:
        return url
    return f"postgresql+asyncpg://{rest}"


def make_async_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(ensure_asyncpg_url(database_url), pool_pre_ping=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def get_engine() -> AsyncEngine:
    """Process-wide engine. Tests should call `make_async_engine` instead."""
    global _engine
    if _engine is None:
        _engine = make_async_engine(get_settings().database_url)
    return _engine


def reset_engine() -> None:
    """Drop the cached engine (used when tests swap DATABASE_URL)."""
    global _engine
    _engine = None
