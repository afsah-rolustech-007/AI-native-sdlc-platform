"""Run the stub graph for one task until interrupt or completion.

Used by the crash-recovery harness and as a manual worker stand-in.

  uv run python scripts/run_graph_task.py --task-id <id>
  uv run python scripts/run_graph_task.py --task-id <id> --resume approve

Exit codes: 0 complete, 10 paused at interrupt, 1 error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from common.config import get_settings
from common.db import make_async_engine, make_session_factory, reset_engine
from common.task_repository import get_task
from common.telemetry import NoOpTelemetrySink
from orchestration.checkpointers.postgres import postgres_checkpointer
from orchestration.dag_constructor import build_graph
from orchestration.runtime import is_complete, is_interrupted, resume_graph, start_or_continue


def chaos_barrier(phase: str) -> None:
    """Block until the parent writes `{phase}.go`. No-op without SDLC_CHAOS_HOOK_DIR."""
    raw = os.environ.get("SDLC_CHAOS_HOOK_DIR")
    if not raw:
        return
    hook_dir = Path(raw)
    hook_dir.mkdir(parents=True, exist_ok=True)
    (hook_dir / f"{phase}.ready").write_text("1", encoding="utf-8")
    go = hook_dir / f"{phase}.go"
    deadline = time.time() + 60
    while not go.exists():
        if time.time() > deadline:
            raise TimeoutError(f"chaos hook timed out waiting for {phase}.go")
        time.sleep(0.02)


async def _run(task_id: str, decision: str | None, checkpointer_kind: str) -> int:
    settings = get_settings()
    reset_engine()
    engine = make_async_engine(settings.database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        task = await get_task(session, task_id)
    if task is None:
        print(f"unknown task_id={task_id}", file=sys.stderr)
        await engine.dispose()
        return 1

    hook = chaos_barrier if os.environ.get("SDLC_CHAOS_HOOK_DIR") else None
    if checkpointer_kind == "memory":
        graph = build_graph(
            checkpointer=InMemorySaver(),
            persist_task_state=True,
            sink=NoOpTelemetrySink(),
            on_node_enter=hook,
        )
        return await _execute(graph, task, decision, engine)

    async with postgres_checkpointer(setup=True) as saver:
        graph = build_graph(
            checkpointer=saver,
            persist_task_state=True,
            sink=NoOpTelemetrySink(),
            on_node_enter=hook,
        )
        return await _execute(graph, task, decision, engine)


async def _execute(graph, task, decision: str | None, engine) -> int:
    if decision:
        snapshot = await resume_graph(graph, task, decision)
    else:
        snapshot = await start_or_continue(graph, task)
    if is_complete(snapshot):
        print(json.dumps({"status": "complete", "task_id": task.id}))
        await engine.dispose()
        return 0
    if is_interrupted(snapshot):
        print(
            json.dumps(
                {
                    "status": "interrupted",
                    "task_id": task.id,
                    "next": list(snapshot.next or ()),
                }
            )
        )
        await engine.dispose()
        return 10
    print(json.dumps({"status": "running", "task_id": task.id, "next": list(snapshot.next or ())}))
    await engine.dispose()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--resume", choices=["approve", "reject"])
    parser.add_argument("--checkpointer", choices=["postgres", "memory"], default="postgres")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.task_id, args.resume, args.checkpointer)))


if __name__ == "__main__":
    main()
