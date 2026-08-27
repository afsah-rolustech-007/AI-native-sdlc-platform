"""Design-phase HITL rehearsal.

`interrupt()` is how LangGraph pauses. The payload only *resembles* `HITLRequest`.
Postgres `hitl_log` is not written here — that bridge is Phase 08 / ApprovalGate.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

from langgraph.types import interrupt

from common.telemetry import TelemetrySink

# Graph wrapper sets this so interrupt() spans use the same sink as phase spans.
_current_sink: ContextVar[TelemetrySink | None] = ContextVar("sdlc_hitl_sink", default=None)

# Close to HITLRequest (§B.2) but not the final schema (no timeout_at / request_id).
DESIGN_APPROVAL_PAYLOAD: dict = {
    "request_type": "approval",
    "phase": "design",
    "reason": "demo approval checkpoint",
    "options": ["approve", "reject"],
    "evidence_ref": "blackboard://demo-design-approval",
}

# Same-process pause→resume can share one HITL span id (wall-clock wait).
_open_hitl_spans: dict[str, str] = {}


def interrupt_for_design_approval(
    task_id: str,
    *,
    sink: TelemetrySink | None = None,
) -> str:
    """Pause at design. Returns the Command(resume=...) value on resume.

    Nodes re-run from the top after resume; we reuse the open span id when this
    process is still alive. A new process starts/ends a short span instead.
    Sink errors never fail the task.
    """
    active = sink if sink is not None else (_current_sink.get() or _get_sink())
    span_id = _open_hitl_spans.get(task_id)
    if span_id is None:
        try:
            span_id = active.start_span(
                kind="hitl",
                name="design_approval",
                task_id=task_id,
                phase="design",
                attributes={"reason": DESIGN_APPROVAL_PAYLOAD["reason"]},
            )
            _open_hitl_spans[task_id] = span_id
        except Exception:
            span_id = "hitl-error"
    decision = interrupt(DESIGN_APPROVAL_PAYLOAD)
    try:
        active.end_span(
            span_id,
            status="ok",
            attributes={"decision": str(decision)},
        )
    except Exception:
        pass
    _open_hitl_spans.pop(task_id, None)
    return str(decision)


def bind_telemetry_sink(sink: TelemetrySink | None) -> Token:
    """Used by wrap_phase_node so HITL spans hit the same sink as phase spans."""
    return _current_sink.set(sink)


def reset_telemetry_sink(token: Token) -> None:
    _current_sink.reset(token)


def _get_sink() -> TelemetrySink:
    from common.tracing import get_sink

    return get_sink()
