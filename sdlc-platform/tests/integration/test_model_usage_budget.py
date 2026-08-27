"""Live-shaped path: InstrumentedAdapter.acomplete writes cost_tracking."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from tests.contract.fakes import FakeAdapter
from tests.factories import make_task

from common.budget import BudgetStatus, BudgetTracker
from common.config import get_settings
from common.db import make_async_engine, make_session_factory, reset_engine
from common.models import CostTrackingRow
from common.task_repository import create_task
from common.telemetry import RecordingTelemetrySink
from model_adapters.base import ChatMessage, ModelRequest
from model_adapters.telemetry import InstrumentedAdapter


async def test_model_call_writes_cost_tracking_and_moves_budget(
    migrated_database_url: str, monkeypatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)
    get_settings.cache_clear()
    reset_engine()

    task = make_task(id="task-model-cost")
    engine = make_async_engine(migrated_database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        await create_task(session, task)
        tracker = BudgetTracker(session)
        sink = RecordingTelemetrySink()
        adapter = InstrumentedAdapter(FakeAdapter(), sink=sink, tracker=tracker)
        await adapter.acomplete(
            ModelRequest(
                messages=[ChatMessage(role="user", content="hi")],
                task_id=task.id,
                phase="implementation",
                agent_id="stub-coder",
                operation="code_generation",
            )
        )
        rows = (
            await session.execute(select(CostTrackingRow).where(CostTrackingRow.task_id == task.id))
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].input_tokens == 10
        assert rows[0].output_tokens == 2
        assert rows[0].cost_usd is not None
        assert float(rows[0].cost_usd) > 0
        assert rows[0].model_id == "fake-small"
        assert sink.started[0]["kind"] == "llm_call"
        status = await tracker.check_budget(task.id)
        assert status is BudgetStatus.OK

        await adapter.aembed(["hello"])
        rows_after_embed = (
            await session.execute(select(CostTrackingRow).where(CostTrackingRow.task_id == task.id))
        ).scalars().all()
        assert len(rows_after_embed) == 1

        await asyncio.gather(
            adapter.acomplete(
                ModelRequest(
                    messages=[ChatMessage(role="user", content="hi")],
                    task_id=task.id,
                    phase="implementation",
                    agent_id="stub-coder",
                    operation="code_generation",
                )
            ),
            adapter.acomplete(
                ModelRequest(
                    messages=[ChatMessage(role="user", content="hi")],
                    task_id=task.id,
                    phase="implementation",
                    agent_id="stub-coder",
                    operation="code_generation",
                )
            ),
        )
        rows_after_concurrent = (
            await session.execute(select(CostTrackingRow).where(CostTrackingRow.task_id == task.id))
        ).scalars().all()
        assert len(rows_after_concurrent) == 3

    await engine.dispose()
    reset_engine()
    get_settings.cache_clear()
