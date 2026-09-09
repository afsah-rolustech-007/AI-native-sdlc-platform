"""ApprovalGate pauses, records decisions, and never auto-approves on timeout."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from tests.factories import make_task

from agents.templates.approval_gate import ApprovalGate, build_approval_gate_node
from common.telemetry import NoOpTelemetrySink
from orchestration.hitl_store import TIMEOUT_ESCALATED, MemoryHitlStore
from orchestration.runtime import interrupt_value, is_interrupted, thread_config
from orchestration.state import SDLCState, initial_sdlc_state


def _graph(node):
    builder = StateGraph(SDLCState)
    builder.add_node("gate", node)
    builder.add_edge(START, "gate")
    builder.add_edge("gate", END)
    return builder.compile(checkpointer=InMemorySaver())


async def _pause(graph, task):
    config = thread_config(task.id)
    await graph.ainvoke(initial_sdlc_state(task), config)
    return await graph.aget_state(config), config


def test_two_checkpoints_are_the_same_class() -> None:
    store = MemoryHitlStore()
    scope = ApprovalGate(checkpoint="scope", store=store, timeout_minutes=5)
    design = ApprovalGate(checkpoint="design", store=store, timeout_minutes=5)
    assert type(scope) is type(design) is ApprovalGate
    assert scope.checkpoint != design.checkpoint
    assert callable(scope.as_node()) and callable(design.as_node())


async def test_approval_gate_pauses_then_records_approve() -> None:
    store = MemoryHitlStore()
    gate = ApprovalGate(
        checkpoint="scope",
        store=store,
        timeout_minutes=30,
        sink=NoOpTelemetrySink(),
    )
    graph = _graph(build_approval_gate_node(gate))
    task = make_task(id="task-gate-approve")
    paused, config = await _pause(graph, task)
    assert is_interrupted(paused)
    payload = interrupt_value(paused)
    assert payload["request_type"] == "approval"
    assert payload["checkpoint"] == "scope"
    assert "approve" in payload["options"]
    assert await store.list_pending()

    await graph.ainvoke(Command(resume="approve"), config)
    snapshot = await graph.aget_state(config)
    assert not is_interrupted(snapshot)
    history = snapshot.values["hitl_history"]
    assert history[-1]["response"] == "approve"
    assert snapshot.values["hitl_queue"] == []
    assert store.approvals()[0]["decision"] == "approve"
    assert not await store.list_pending()


async def test_timeout_escalation_never_resolves_to_approved() -> None:
    store = MemoryHitlStore()
    past = datetime.now(UTC) - timedelta(minutes=1)
    await store.insert_open(
        {
            "request_id": "req-timeout-1",
            "task_id": "task-timeout",
            "request_type": "approval",
            "phase": "requirements",
            "reason": "scope approval checkpoint",
            "evidence_ref": "hitl://task-timeout/scope/req-timeout-1",
            "options": ["approve", "reject_with_feedback", "request_changes"],
            "checkpoint": "scope",
            "timeout_at": past,
        }
    )
    escalated = await store.escalate_expired(datetime.now(UTC))
    assert escalated
    assert all(row["response"] == TIMEOUT_ESCALATED for row in escalated)
    assert all(row["response"] != "approve" for row in escalated)
    assert store.approvals() == []
    pending = await store.list_pending()
    assert pending[0]["response"] == TIMEOUT_ESCALATED
    assert pending[0]["responded_at"] is None


async def test_applies_when_false_skips_interrupt() -> None:
    store = MemoryHitlStore()
    gate = ApprovalGate(
        checkpoint="scope",
        store=store,
        applies_when=lambda _state: False,
        sink=NoOpTelemetrySink(),
    )
    graph = _graph(build_approval_gate_node(gate))
    task = make_task(id="task-gate-skip")
    snapshot, _config = await _pause(graph, task)
    assert not is_interrupted(snapshot)
    assert await store.list_pending() == []
