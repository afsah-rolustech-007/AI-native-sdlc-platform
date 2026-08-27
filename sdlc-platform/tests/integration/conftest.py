"""Postgres and Redis fixtures for Phase 00 integration tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from common.config import get_settings
from common.db import ensure_asyncpg_url, make_async_engine, make_session_factory

ROOT = Path(__file__).resolve().parents[2]


def _asyncpg_url(raw: str) -> str:
    return ensure_asyncpg_url(raw)


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        yield _asyncpg_url(postgres.get_connection_url())


@pytest.fixture(scope="session")
def migrated_database_url(postgres_url: str) -> Iterator[str]:
    os.environ["DATABASE_URL"] = postgres_url
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["ENVIRONMENT"] = "test"
    get_settings.cache_clear()
    cfg = Config(str(ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")
    yield postgres_url


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    with RedisContainer("redis:7.2") as redis:
        host = redis.get_container_host_ip()
        port = redis.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest.fixture
async def db_session(migrated_database_url: str) -> AsyncIterator[AsyncSession]:
    engine = make_async_engine(migrated_database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        yield session
        await session.rollback()
        await session.execute(text("TRUNCATE TABLE cost_tracking, hitl_log, approvals, tasks CASCADE"))
        await session.commit()
    await engine.dispose()
