"""ARQ ping_task processes a job and writes a zero-cost row."""

from __future__ import annotations

from arq.connections import create_pool
from arq.worker import Worker
from sqlalchemy import func, select
from tests.factories import make_task

from common.budget import BudgetTracker
from common.config import get_settings
from common.db import make_async_engine, make_session_factory, reset_engine
from common.models import CostTrackingRow
from common.task_repository import create_task
from worker.main import ping_task, redis_settings_from_config, shutdown, startup


async def test_ping_task_emits_side_effects(
    migrated_database_url: str, redis_url: str, monkeypatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)
    monkeypatch.setenv("REDIS_URL", redis_url)
    get_settings.cache_clear()
    reset_engine()

    engine = make_async_engine(migrated_database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        await create_task(session, make_task(id="task-worker-1"))

    settings = redis_settings_from_config()
    pool = await create_pool(settings)
    job = await pool.enqueue_job("ping_task", "task-worker-1")
    assert job is not None

    worker = Worker(
        functions=[ping_task],
        redis_pool=pool,
        burst=True,
        on_startup=startup,
        on_shutdown=shutdown,
    )
    await worker.main()

    async with factory() as session:
        count = await session.execute(
            select(func.count(CostTrackingRow.id)).where(
                CostTrackingRow.task_id == "task-worker-1",
                CostTrackingRow.agent_id == "ping_task",
            )
        )
        assert count.scalar_one() == 1
        tracker = BudgetTracker(session, max_node_visits=50)
        status = await tracker.check_budget("task-worker-1")
        assert status.value == "ok"

    await engine.dispose()
    await pool.aclose()
    reset_engine()
    get_settings.cache_clear()
