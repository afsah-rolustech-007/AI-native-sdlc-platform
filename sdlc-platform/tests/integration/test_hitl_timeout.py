"""Fail-closed HITL timeout against real hitl_log — never writes approve."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from tests.factories import make_task

from common.config import get_settings
from common.db import make_async_engine, make_session_factory, reset_engine
from common.models import ApprovalRow, HitlLogRow
from common.task_repository import create_task
from orchestration.hitl_store import TIMEOUT_ESCALATED, PostgresHitlStore
from worker.hitl_jobs import escalate_expired_hitl


async def test_expired_hitl_escalates_without_approval_row(
    migrated_database_url: str, monkeypatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)
    get_settings.cache_clear()
    reset_engine()

    task = make_task(id="task-hitl-timeout")
    engine = make_async_engine(migrated_database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        await create_task(session, task)

    store = PostgresHitlStore(session_factory=factory)
    past = datetime.now(UTC) - timedelta(minutes=5)
    row = await store.insert_open(
        {
            "task_id": task.id,
            "request_type": "approval",
            "phase": "requirements",
            "reason": "scope approval checkpoint",
            "evidence_ref": "hitl://task-hitl-timeout/scope/x",
            "options": ["approve", "reject_with_feedback", "request_changes"],
            "checkpoint": "scope",
            "timeout_at": past,
        }
    )
    result = await escalate_expired_hitl({"engine": engine})
    assert result["approved"] == 0
    assert row["request_id"] in result["request_ids"]

    async with factory() as session:
        hitl = await session.execute(
            select(HitlLogRow).where(HitlLogRow.task_id == task.id)
        )
        logged = hitl.scalar_one()
        assert logged.response == TIMEOUT_ESCALATED
        assert logged.responded_by == "system:timeout"
        assert logged.responded_at is None
        approvals = await session.execute(
            select(ApprovalRow).where(ApprovalRow.task_id == task.id)
        )
        assert approvals.scalars().first() is None
        assert logged.response != "approve"

    await engine.dispose()
    reset_engine()
    get_settings.cache_clear()
