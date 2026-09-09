"""Human approval checkpoint as config, not a new agent class.

Think of this as a form: "show this evidence, offer these buttons, wait."
Scope vs design vs release are the *same* code with different `checkpoint`
values. Do not subclass this for one special gate — add a config field instead.

This is not a BaseAgent. It does not call an LLM. It only pauses the graph.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agents.templates.evidence import EvidenceBuilder, EvidenceBundleSpec, assemble_evidence_bundle
from orchestration.hitl import interrupt_with_span
from orchestration.hitl_store import (
    TIMEOUT_ESCALATED,
    HitlStore,
    MemoryHitlStore,
    PostgresHitlStore,
    utcnow,
)
from orchestration.state import HITLRequest, SDLCState

Checkpoint = Literal["scope", "design", "security", "release", "pr", "deployment"]
DEFAULT_DECISIONS: tuple[str, ...] = ("approve", "reject_with_feedback", "request_changes")

# Maps the gate name to the SDLC phase we stamp on the hitl_log row.
# "scope" is the sign-off at the end of requirements (wired in Section 05).
_CHECKPOINT_PHASE: dict[str, str] = {
    "scope": "requirements",
    "design": "design",
    "security": "design",
    "release": "qa",
    "pr": "review",
    "deployment": "release",
}


class ApprovalGate(BaseModel):
    """Settings for one pause. Call `as_node()` to get a LangGraph node function.

    checkpoint: which sign-off this is (scope, design, ...).
    applies_when: if this returns False, skip the pause and continue.
    timeout_minutes: after this, a worker job holds the task — it never auto-approves.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    checkpoint: Checkpoint
    evidence_bundle_spec: EvidenceBundleSpec = Field(default_factory=EvidenceBundleSpec)
    applies_when: Callable[[SDLCState], bool] | None = None
    decision_options: list[str] = Field(default_factory=lambda: list(DEFAULT_DECISIONS))
    timeout_minutes: int = 60
    store: Any = None
    extra_builders: dict[str, EvidenceBuilder] = Field(default_factory=dict)
    phase: str | None = None
    sink: Any = None

    def as_node(self) -> Callable[[SDLCState], Any]:
        return build_approval_gate_node(self)


def build_approval_gate_node(config: ApprovalGate) -> Callable[[SDLCState], Any]:
    """Turn config into a graph node. Scope and design share this function."""
    store = config.store if config.store is not None else PostgresHitlStore()
    phase = config.phase or _CHECKPOINT_PHASE[config.checkpoint]
    applies = config.applies_when or (lambda _state: True)

    async def approval_gate_node(state: SDLCState) -> dict:
        # Optional skip, e.g. "only fire for medium+ risk" later.
        if not applies(state):
            return {}
        task_id = state["task_id"]
        # Packet shown to the human: what they are signing off on.
        bundle = assemble_evidence_bundle(
            state,
            config.evidence_bundle_spec,
            checkpoint=config.checkpoint,
            extra_builders=config.extra_builders,
        )
        record = await _ensure_open_row(store, config, state, phase, bundle)
        payload = _interrupt_payload(record, bundle)
        # interrupt() pauses the whole graph (like a breakpoint).
        # On resume LangGraph restarts THIS function from the top, then
        # interrupt() returns the human's string (approve / reject / ...).
        # Writing hitl_log *before* interrupt is required; the insert is
        # idempotent so the restart does not duplicate the question.
        decision = interrupt_with_span(
            task_id,
            payload,
            name=f"approval_{config.checkpoint}",
            phase=phase,
            sink=config.sink,
        )
        return await _on_resume(store, config, state, record, decision)

    approval_gate_node.__name__ = f"approval_gate_{config.checkpoint}"
    approval_gate_node.__qualname__ = approval_gate_node.__name__
    return approval_gate_node


def default_memory_gate(checkpoint: Checkpoint, **kwargs: Any) -> ApprovalGate:
    """Test helper: never touches Postgres."""
    return ApprovalGate(checkpoint=checkpoint, store=MemoryHitlStore(), **kwargs)


async def _ensure_open_row(
    store: HitlStore,
    config: ApprovalGate,
    state: SDLCState,
    phase: str,
    bundle: dict[str, Any],
) -> dict[str, Any]:
    existing = await store.get_open(task_id=state["task_id"], checkpoint=config.checkpoint)
    if existing is not None:
        return existing
    request_id = str(uuid4())
    now = utcnow()
    return await store.insert_open(
        {
            "request_id": request_id,
            "task_id": state["task_id"],
            "request_type": "approval",
            "phase": phase,
            "reason": f"{config.checkpoint} approval checkpoint",
            "evidence_ref": f"hitl://{state['task_id']}/{config.checkpoint}/{request_id}",
            "options": list(config.decision_options),
            "checkpoint": config.checkpoint,
            "timeout_at": now + timedelta(minutes=config.timeout_minutes),
            "bundle_keys": list(bundle.keys()),
        }
    )


def _interrupt_payload(record: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    timeout_at = record["timeout_at"]
    timeout_s = timeout_at.isoformat() if hasattr(timeout_at, "isoformat") else str(timeout_at)
    return {
        "request_id": record["request_id"],
        "request_type": "approval",
        "phase": record["phase"],
        "reason": record["reason"],
        "evidence_ref": record["evidence_ref"],
        "options": list(record["options"]),
        "timeout_at": timeout_s,
        "checkpoint": record["checkpoint"],
        "evidence_bundle": bundle,
    }


async def _on_resume(
    store: HitlStore,
    config: ApprovalGate,
    state: SDLCState,
    record: dict[str, Any],
    decision: str,
) -> dict:
    now = utcnow()
    normalized = decision.strip()
    # The timeout job never resumes the graph. If somehow the resume value is
    # the timeout token, do not treat that as a human "approve".
    if normalized == TIMEOUT_ESCALATED or _timeout_blocks_approve(record, normalized):
        return _timeout_updates(state, record, now)
    await store.mark_responded(
        record["request_id"],
        response=normalized,
        responded_by="human",
        responded_at=now,
    )
    if normalized in config.decision_options:
        # Durable audit row: who said what at this checkpoint.
        await store.record_approval(
            task_id=state["task_id"],
            checkpoint=config.checkpoint,
            approver="human",
            decision=normalized,
            evidence_ref=record["evidence_ref"],
            decided_at=now,
        )
    completed = _hitl_request(record, response=normalized, responded_by="human", responded_at=now)
    # hitl_queue = still waiting. Remove this request now that it is answered.
    # hitl_history is append-only, so we return only the new completed item.
    remaining = [
        item
        for item in (state.get("hitl_queue") or [])
        if item.get("request_id") != record["request_id"]
    ]
    return {
        "hitl_queue": remaining,
        "hitl_history": [completed],
        "agent_events": [_decision_event(state, config.checkpoint, normalized)],
    }


def _timeout_blocks_approve(record: dict[str, Any], decision: str) -> bool:
    """A timeout mark plus an empty/approve-shaped auto resume must not approve."""
    if record.get("response") != TIMEOUT_ESCALATED:
        return False
    return decision.lower() in {"", TIMEOUT_ESCALATED}


def _timeout_updates(state: SDLCState, record: dict[str, Any], now) -> dict:
    # Fail-closed: no ApprovalRecord, and do not append history as "approved".
    remaining = [
        item
        for item in (state.get("hitl_queue") or [])
        if item.get("request_id") != record["request_id"]
    ]
    return {
        "hitl_queue": remaining,
        "agent_events": [
            _decision_event(state, str(record.get("checkpoint") or ""), TIMEOUT_ESCALATED)
        ],
    }


def _hitl_request(
    record: dict[str, Any],
    *,
    response: str | None,
    responded_by: str | None,
    responded_at: Any,
) -> HITLRequest:
    return {
        "request_id": str(record["request_id"]),
        "request_type": "approval",
        "phase": str(record["phase"]),
        "reason": str(record["reason"]),
        "evidence_ref": str(record["evidence_ref"]),
        "options": list(record["options"]),
        "response": response,
        "responded_by": responded_by,
        "responded_at": responded_at,
        "timeout_at": record["timeout_at"],
    }


def _decision_event(state: SDLCState, checkpoint: str, decision: str) -> dict[str, Any]:
    # Observational only — UI/audit. Never used to route the graph.
    return {
        "event_id": uuid4().hex,
        "task_id": state["task_id"],
        "timestamp": utcnow().isoformat(),
        "agent_id": f"approval_gate:{checkpoint}",
        "phase": _CHECKPOINT_PHASE.get(checkpoint, checkpoint),
        "span_id": None,
        "parent_span_id": None,
        "event_type": "hitl_responded",
        "payload": {"checkpoint": checkpoint, "decision": decision},
    }
