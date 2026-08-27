"""Phase 00 live demo: Task → Postgres → sandbox → budget → optional worker ping.

Requires Docker (sandbox), Postgres, and Redis:
  make up && make migrate
  uv run python scripts/demo_phase0.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from common.budget import BudgetStatus, BudgetTracker, KillSwitchError
from common.config import get_settings
from common.db import make_async_engine, make_session_factory
from common.models import CostTrackingRow
from common.sandbox import list_sandbox_container_ids, run_in_sandbox
from common.task import Methodology, RepoRef, RiskTier, Task, TaskBudget, TaskState, WorkType
from common.task_repository import create_task, get_task, update_task_state
from common.tracing import get_sink, reset_sink


async def _run(breach: bool) -> None:
    reset_sink()
    get_sink()
    settings = get_settings()
    engine = make_async_engine(settings.database_url)
    factory = make_session_factory(engine)
    task_id = "demo-phase0-breach" if breach else "demo-phase0-ok"
    budget = TaskBudget(cost_ceiling_usd=0.01 if breach else 20.0, token_ceiling=2_000_000)
    async with factory() as session:
        task = Task(
            id=task_id,
            title="Phase 00 dummy task",
            source="user_request",
            type=WorkType.FEATURE,
            methodology=Methodology.AGILE,
            repo_refs=[RepoRef(repo_id="demo/app", architecture="monolith")],
            risk_tier=RiskTier.LOW,
            budget=budget,
        )
        stored = await create_task(session, task)
        print(f"created task {stored.id} state={stored.state.value}")

        result = run_in_sandbox(
            stored.id,
            ["sh", "-c", "echo hello && sleep 1"],
            timeout_s=30,
        )
        print(
            f"sandbox exit={result.exit_code} timed_out={result.timed_out} "
            f"stdout={result.stdout.strip()!r} leftover={list_sandbox_container_ids(stored.id)}"
        )

        tracker = BudgetTracker(session)
        await tracker.record(
            stored.id,
            "intake",
            "demo_sandbox",
            input_tokens=10,
            output_tokens=10,
            cost_usd=0.02,
            latency_ms=result.duration_ms,
            idempotency_key=f"demo:{stored.id}:sandbox",
        )
        status = await tracker.check_budget(stored.id)
        print(f"budget status={status.value}")
        if status is BudgetStatus.EXCEEDED:
            try:
                await tracker.enforce_budget(stored.id)
            except KillSwitchError as exc:
                updated = await update_task_state(session, stored.id, TaskState.BLOCKED)
                print(f"kill-switch: {exc} → state={updated.state.value}")
        else:
            updated = await update_task_state(session, stored.id, TaskState.DONE)
            print(f"within budget → state={updated.state.value}")

        rows = await session.execute(
            select(CostTrackingRow).where(CostTrackingRow.task_id == stored.id)
        )
        print("cost_tracking:")
        for row in rows.scalars():
            print(f"  agent={row.agent_id} cost_usd={row.cost_usd} tokens={row.input_tokens}+{row.output_tokens}")
        reloaded = await get_task(session, stored.id)
        print(f"final task state={reloaded.state.value if reloaded else 'missing'}")

        try:
            from arq.connections import create_pool

            from worker.main import redis_settings_from_config

            pool = await create_pool(redis_settings_from_config())
            job = await pool.enqueue_job("ping_task", stored.id)
            print(f"enqueued ping_task job={getattr(job, 'job_id', job)}")
            await pool.aclose()
        except Exception as exc:
            print(f"worker enqueue skipped: {exc}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--breach",
        action="store_true",
        help="Use a tiny cost ceiling so the kill-switch trips (blocked).",
    )
    args = parser.parse_args()
    asyncio.run(_run(breach=args.breach))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
