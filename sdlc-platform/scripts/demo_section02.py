"""Section 02/03 demo: persist, pause at design, new connection, resume.

Requires Postgres:
  make up && make migrate
  uv run python scripts/demo_section02.py
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from common.config import get_settings
from common.db import make_async_engine, make_session_factory
from common.task import Methodology, RepoRef, RiskTier, Task, WorkType
from common.task_repository import create_task, get_task
from common.telemetry import NoOpTelemetrySink
from orchestration.checkpointers.postgres import get_thread_id, postgres_checkpointer
from orchestration.dag_constructor import build_graph
from orchestration.runtime import interrupt_value, is_complete, resume_graph, start_or_continue


async def _run() -> None:
    settings = get_settings()
    engine = make_async_engine(settings.database_url)
    factory = make_session_factory(engine)
    task = Task(
        id="demo-phase01-s02",
        title="Phase 01 checkpoint demo",
        source="user_request",
        type=WorkType.FEATURE,
        methodology=Methodology.AGILE,
        repo_refs=[RepoRef(repo_id="demo/app", architecture="monolith")],
        risk_tier=RiskTier.LOW,
    )
    async with factory() as session:
        existing = await get_task(session, task.id)
        if existing is None:
            await create_task(session, task)

    thread_id = get_thread_id(task)

    async with postgres_checkpointer(setup=True) as saver:
        graph = build_graph(checkpointer=saver, persist_task_state=True, sink=NoOpTelemetrySink())
        snapshot = await start_or_continue(graph, task)
        print(
            f"process A: paused next={snapshot.next} "
            f"interrupt={interrupt_value(snapshot)}"
        )

    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT thread_id, COUNT(*) AS n FROM checkpoints "
                "WHERE thread_id = :tid GROUP BY thread_id"
            ),
            {"tid": thread_id},
        )
        for row in rows:
            print(f"checkpoints: thread_id={row.thread_id} count={row.n}")

    async with postgres_checkpointer(setup=False) as saver:
        graph = build_graph(
            checkpointer=saver, persist_task_state=True, sink=NoOpTelemetrySink()
        )
        snapshot = await resume_graph(graph, task, "approve")
        phases = [event["phase"] for event in snapshot.values["agent_events"] if event["event_type"] == "phase_completed"]
        print(f"process B: complete={is_complete(snapshot)} phases={phases}")

    async with factory() as session:
        stored = await get_task(session, task.id)
        print(f"postgres tasks.state={stored.state.value if stored else 'missing'}")
    await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sys.exit(130)
