"""Resume a task paused at the design interrupt.

  uv run python scripts/resume_task.py <task_id> approve|reject

Requires Postgres (make up && make migrate). Uses a new process/connection.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from common.config import get_settings
from common.db import make_async_engine, make_session_factory
from common.task_repository import get_task
from common.telemetry import NoOpTelemetrySink
from orchestration.checkpointers.postgres import postgres_checkpointer
from orchestration.dag_constructor import build_graph
from orchestration.runtime import interrupt_value, is_complete, resume_graph, thread_config


async def _run(task_id: str, decision: str) -> None:
    settings = get_settings()
    engine = make_async_engine(settings.database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        task = await get_task(session, task_id)
    if task is None:
        raise SystemExit(f"unknown task_id={task_id}")

    async with postgres_checkpointer(setup=True) as saver:
        graph = build_graph(checkpointer=saver, persist_task_state=True, sink=NoOpTelemetrySink())
        config = thread_config(task.id)
        snapshot = await graph.aget_state(config)
        payload = interrupt_value(snapshot)
        print(f"thread_id={task.id} next={snapshot.next}")
        print("pending interrupt payload:")
        print(json.dumps(payload, indent=2, default=str))
        if payload is None:
            raise SystemExit("graph is not waiting on interrupt(); nothing to resume")
        snapshot = await resume_graph(graph, task, decision)
        print(f"after resume next={snapshot.next} complete={is_complete(snapshot)}")
        events = snapshot.values.get("agent_events") or []
        print("agent_events:")
        for event in events:
            print(f"  {event.get('event_type')} phase={event.get('phase')} payload={event.get('payload')}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Resume a design-phase HITL interrupt")
    parser.add_argument("task_id")
    parser.add_argument("decision", choices=["approve", "reject"])
    args = parser.parse_args()
    asyncio.run(_run(args.task_id, args.decision))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
