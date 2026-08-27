"""Section 01 demo: stub graph with design interrupt, then auto-approve.

  uv run python scripts/demo_section01.py
"""

from __future__ import annotations

import asyncio
import json

from langgraph.checkpoint.memory import InMemorySaver

from common.task import Methodology, RepoRef, RiskTier, Task, WorkType
from common.telemetry import NoOpTelemetrySink
from orchestration.dag_constructor import build_graph
from orchestration.runtime import is_interrupted, run_to_completion, start_or_continue


async def _run() -> None:
    task = Task(
        id="demo-phase01-s01",
        title="Phase 01 stub walk",
        source="user_request",
        type=WorkType.FEATURE,
        methodology=Methodology.AGILE,
        repo_refs=[RepoRef(repo_id="demo/app", architecture="monolith")],
        risk_tier=RiskTier.LOW,
    )
    graph = build_graph(
        checkpointer=InMemorySaver(),
        persist_task_state=False,
        sink=NoOpTelemetrySink(),
    )
    paused = await start_or_continue(graph, task)
    print(f"paused next={paused.next} interrupted={is_interrupted(paused)}")
    snapshot = await run_to_completion(graph, task, decision="approve")
    events = snapshot.values["agent_events"]
    print(f"task_id={snapshot.values['task_id']}")
    print("agent_events:")
    print(
        json.dumps(
            [
                {
                    "phase": event["phase"],
                    "event_type": event["event_type"],
                    "payload": event.get("payload"),
                }
                for event in events
            ],
            indent=2,
        )
    )
    print(f"count={len(events)}")


if __name__ == "__main__":
    asyncio.run(_run())
