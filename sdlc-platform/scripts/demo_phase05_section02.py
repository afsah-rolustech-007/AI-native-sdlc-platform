"""Phase 05 §02 demo: ApprovalGate approve vs fail-closed timeout.

  uv run python scripts/demo_phase05_section02.py
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from agents.templates.approval_gate import ApprovalGate, build_approval_gate_node
from common.task import Methodology, RepoRef, RiskTier, Task, WorkType
from common.telemetry import NoOpTelemetrySink
from orchestration.hitl_store import TIMEOUT_ESCALATED, MemoryHitlStore
from orchestration.runtime import interrupt_value, is_interrupted, thread_config
from orchestration.state import SDLCState, initial_sdlc_state


def _task(task_id: str) -> Task:
    return Task(
        id=task_id,
        title="Demo gate",
        source="user_request",
        type=WorkType.FEATURE,
        methodology=Methodology.AGILE,
        repo_refs=[RepoRef(repo_id="demo/app", architecture="monolith")],
        risk_tier=RiskTier.LOW,
        created_at=datetime.now(UTC),
    )


def _graph(node):
    builder = StateGraph(SDLCState)
    builder.add_node("gate", node)
    builder.add_edge(START, "gate")
    builder.add_edge("gate", END)
    return builder.compile(checkpointer=InMemorySaver())


async def _approve_flow() -> None:
    store = MemoryHitlStore()
    gate = ApprovalGate(
        checkpoint="scope",
        store=store,
        timeout_minutes=30,
        sink=NoOpTelemetrySink(),
    )
    graph = _graph(build_approval_gate_node(gate))
    task = _task("demo-gate-approve")
    config = thread_config(task.id)
    await graph.ainvoke(initial_sdlc_state(task), config)
    paused = await graph.aget_state(config)
    print("1. ApprovalGate(scope) paused")
    print(f"   payload.request_type={interrupt_value(paused)['request_type']}")
    print(f"   pending hitl_log rows={len(await store.list_pending())}")
    await graph.ainvoke(Command(resume="approve"), config)
    done = await graph.aget_state(config)
    print(f"2. resumed approve; interrupted={is_interrupted(done)}")
    print(f"   ApprovalRecord.decision={store.approvals()[0]['decision']}")
    print(f"   hitl_history.response={done.values['hitl_history'][-1]['response']}")


async def _timeout_flow() -> None:
    store = MemoryHitlStore()
    await store.insert_open(
        {
            "request_id": "demo-timeout",
            "task_id": "demo-gate-timeout",
            "request_type": "approval",
            "phase": "requirements",
            "reason": "scope approval checkpoint",
            "evidence_ref": "hitl://demo/scope/demo-timeout",
            "options": ["approve", "reject_with_feedback", "request_changes"],
            "checkpoint": "scope",
            "timeout_at": datetime.now(UTC) - timedelta(seconds=1),
        }
    )
    escalated = await store.escalate_expired()
    print("3. timeout job ran (no graph resume)")
    print(f"   escalated={len(escalated)} response={escalated[0]['response']}")
    print(f"   approvals written={store.approvals()}")
    print(f"   auto-approved={any(row['response'] == 'approve' for row in escalated)}")
    assert escalated[0]["response"] == TIMEOUT_ESCALATED
    assert store.approvals() == []


async def main() -> None:
    await _approve_flow()
    await _timeout_flow()


if __name__ == "__main__":
    asyncio.run(main())
