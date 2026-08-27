"""LangGraph node wrapper → TelemetrySink only (`final_plan.md` §B.8.5).

This file is the only orchestration-to-telemetry bridge. Graph nodes never import
OpenTelemetry. If the orchestrator is replaced later, only this adapter changes.

On entry: optional chaos hook, start a `kind="phase"` span, then `update_task_state`.
On exit: append one `AgentEvent` and end the span.
On `interrupt()`: GraphInterrupt is re-raised (pause). HITL span start/end lives in
`hitl.py` around the interrupt() call itself.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langgraph.errors import GraphInterrupt

from common.db import get_engine, make_session_factory
from common.task import TaskState
from common.task_repository import update_task_state
from common.telemetry import TelemetrySink
from orchestration.hitl import bind_telemetry_sink, reset_telemetry_sink
from orchestration.state import SDLCState

NodeFn = Callable[[SDLCState], dict | Awaitable[dict]]
NodeEnterHook = Callable[[str], None]


def wrap_phase_node(
    phase: str,
    node_fn: NodeFn,
    *,
    persist_task_state: bool = True,
    sink: TelemetrySink | None = None,
    on_node_enter: NodeEnterHook | None = None,
) -> Callable[[SDLCState], Awaitable[dict]]:
    """Wrap a stub (or later, a real manager) with phase span + Task.state sync."""

    async def wrapped(state: SDLCState) -> dict:
        if on_node_enter is not None:
            on_node_enter(phase)
        task_id = state["task_id"]
        active_sink = sink if sink is not None else _get_sink()
        span_id = active_sink.start_span(
            kind="phase",
            name=phase,
            task_id=task_id,
            phase=phase,
            attributes={"model_id": None, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0},
        )
        sink_token = bind_telemetry_sink(active_sink)
        try:
            if persist_task_state:
                await _persist_phase(task_id, TaskState(phase))
            updates = await _call_node(node_fn, state)
            if phase == "monitoring" and persist_task_state:
                await _persist_phase(task_id, TaskState.DONE)
            extra_events = list(updates.pop("agent_events", []) or [])
            event = _phase_event(task_id, phase, span_id)
            active_sink.end_span(span_id, status="ok")
            return {**updates, "agent_events": [*extra_events, event]}
        except GraphInterrupt:
            # Pause for HITL. Not a node failure.
            active_sink.end_span(span_id, status="cancelled")
            raise
        except Exception as exc:
            active_sink.end_span(
                span_id,
                status="error",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            raise
        finally:
            reset_telemetry_sink(sink_token)

    wrapped.__name__ = f"{phase}_node"
    wrapped.__qualname__ = f"wrap_phase_node.<locals>.{phase}_node"
    return wrapped


async def _call_node(node_fn: NodeFn, state: SDLCState) -> dict:
    result: Any = node_fn(state)
    if inspect.isawaitable(result):
        result = await result
    return dict(result or {})


async def _persist_phase(task_id: str, phase: TaskState) -> None:
    engine = get_engine()
    factory = make_session_factory(engine)
    async with factory() as session:
        await update_task_state(session, task_id, phase)


def _phase_event(task_id: str, phase: str, span_id: str) -> dict:
    """One UI AgentEvent per stub node. Observational only — never used for routing."""
    return {
        "event_id": uuid4().hex,
        "task_id": task_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "agent_id": f"stub:{phase}",
        "phase": phase,
        "span_id": span_id,
        "parent_span_id": None,
        "event_type": "phase_completed",
        "payload": {},
    }


def _get_sink() -> TelemetrySink:
    from common.tracing import get_sink

    return get_sink()
