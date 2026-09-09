"""Pause the graph for a human (`interrupt()`) and record a tracing span.

`interrupt()` = *how* we pause (LangGraph primitive).
`hitl_log` / HITLRequest = *what* we ask the human (data).

The Phase 01 design stub still does not write Postgres. ApprovalGate does.
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


def interrupt_with_span(
    task_id: str,
    payload: dict,
    *,
    name: str,
    phase: str,
    sink: TelemetrySink | None = None,
) -> str:
    """Pause here until Command(resume=decision) is issued.

    First visit: interrupt() raises GraphInterrupt → graph stops.
    After resume: this function runs again from the top, then interrupt()
    *returns* the human's string instead of pausing.
    """
    active = sink if sink is not None else (_current_sink.get() or _get_sink())
    span_key = f"{task_id}:{name}"
    span_id = _open_hitl_spans.get(span_key)
    if span_id is None:
        try:
            span_id = active.start_span(
                kind="hitl",
                name=name,
                task_id=task_id,
                phase=phase,
                attributes={"reason": str(payload.get("reason") or name)},
            )
            _open_hitl_spans[span_key] = span_id
        except Exception:
            span_id = "hitl-error"
    # This is the actual pause. Everything above re-runs after resume.
    decision = interrupt(payload)
    try:
        active.end_span(
            span_id,
            status="ok",
            attributes={"decision": str(decision)},
        )
    except Exception:
        pass
    _open_hitl_spans.pop(span_key, None)
    return str(decision)


def interrupt_for_design_approval(
    task_id: str,
    *,
    sink: TelemetrySink | None = None,
) -> str:
    """Phase 01 stub pause. Real checkpoints use ApprovalGate + hitl_log."""
    return interrupt_with_span(
        task_id,
        DESIGN_APPROVAL_PAYLOAD,
        name="design_approval",
        phase="design",
        sink=sink,
    )


def bind_telemetry_sink(sink: TelemetrySink | None) -> Token:
    """Used by wrap_phase_node so HITL spans hit the same sink as phase spans."""
    return _current_sink.set(sink)


def reset_telemetry_sink(token: Token) -> None:
    _current_sink.reset(token)


def _get_sink() -> TelemetrySink:
    from common.tracing import get_sink

    return get_sink()
