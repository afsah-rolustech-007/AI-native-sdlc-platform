"""AsyncPostgresSaver wiring (`final_plan.md` §D checkpointing).

LangGraph owns tables `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`
(and `checkpoint_migrations`). Alembic does not manage them — call
`setup_checkpoint_tables()` once (see `scripts/init_langgraph_tables.py`).

`thread_id` is `task.id`. Phase 00 already caps Task.id at 255 characters, so
this module does not truncate. Silent `id[:255]` here would hide collisions.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from common.config import get_settings
from common.task import Task


def get_thread_id(task: Task) -> str:
    """Return `task.id` unchanged. Fail if a caller somehow exceeds 255 chars."""
    if len(task.id) > 255:
        raise ValueError(f"thread_id exceeds 255 characters: {len(task.id)}")
    return task.id


def checkpoint_conn_string(database_url: str | None = None) -> str:
    """psycopg connection string. SQLAlchemy's `+asyncpg` driver suffix is stripped."""
    url = database_url if database_url is not None else get_settings().database_url
    _, sep, rest = url.partition("://")
    if not sep:
        return url
    return f"postgresql://{rest}"


@asynccontextmanager
async def postgres_checkpointer(
    database_url: str | None = None,
    *,
    setup: bool = False,
) -> AsyncIterator[AsyncPostgresSaver]:
    """Open a saver against the platform Postgres. `setup=True` creates tables."""
    async with AsyncPostgresSaver.from_conn_string(
        checkpoint_conn_string(database_url)
    ) as saver:
        if setup:
            await saver.setup()
        yield saver


async def setup_checkpoint_tables(database_url: str | None = None) -> None:
    """Idempotent: create LangGraph checkpoint tables if they are missing."""
    async with postgres_checkpointer(database_url, setup=True):
        return
