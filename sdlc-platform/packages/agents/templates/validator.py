"""Independent check after another agent finishes.

The producing agent (e.g. Requirements Analyst) must not grade its own homework.
This node only sees `SDLCState`, looks up a named rule, and never takes a cached
copy of the producer's model response.

Same class for every phase. Swap `rule_set` / `on_failure`. Section 05 will
register the real `consistency-checker`; until then that name fail-closes.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from orchestration.hitl import interrupt_with_span
from orchestration.hitl_store import HitlStore, PostgresHitlStore, utcnow
from orchestration.state import SDLCState, ValidationFlag

ValidatorPhase = Literal["requirements", "design", "implementation", "qa"]
OnFailure = Literal["feedback_loop", "hitl", "suspend"]
RuleFn = Callable[[SDLCState], "ValidatorResult | Awaitable[ValidatorResult]"]

# Names from the blueprint. Register a real function before using them.
# Unknown name → fail closed (treat as error), never "looks fine".
RESERVED_RULE_SETS: frozenset[str] = frozenset(
    {
        "consistency-checker",
        "design-checklist",
        "static-analysis",
        "qa-plan-compliance",
    }
)

_RULE_SETS: dict[str, RuleFn] = {}


class ValidatorResult(BaseModel):
    passed: bool
    flags: list[ValidationFlag] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    findings: list[dict] = Field(default_factory=list)


class Validator(BaseModel):
    """Settings for one check. `as_node()` → LangGraph node.

    independent_of: name of the agent whose output we are checking.
    on_failure: feedback_loop (send gaps back), hitl (ask a human), or suspend.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    phase: ValidatorPhase
    rule_set: str
    independent_of: str
    on_failure: OnFailure = "feedback_loop"
    store: Any = None
    sink: Any = None
    timeout_minutes: int = 60

    def as_node(self) -> Callable[[SDLCState], Any]:
        return build_validator_node(self)


def register_rule_set(name: str, fn: RuleFn) -> None:
    """Plug in a check function. Section 05 registers `consistency-checker` here."""
    _RULE_SETS[name] = fn


def unregister_rule_set(name: str) -> None:
    _RULE_SETS.pop(name, None)


def registered_rule_sets() -> tuple[str, ...]:
    return tuple(_RULE_SETS)


def build_validator_node(config: Validator) -> Callable[[SDLCState], Any]:
    """Turn config into a graph node. Each call gets a new inner function (fresh scope)."""
    store = config.store if config.store is not None else PostgresHitlStore()

    async def validator_node(state: SDLCState) -> dict:
        # Fresh call each time. The producer’s ModelResponse is not in this scope.
        result = await _run_rule(config.rule_set, config.phase, state)
        if result.passed:
            return {
                "agent_events": [_event(state, config, "validator_passed", result)],
            }
        return await _on_failure(config, store, state, result)

    validator_node.__name__ = f"validator_{config.phase}_{config.rule_set}"
    validator_node.__qualname__ = validator_node.__name__
    return validator_node


async def _run_rule(name: str, phase: str, state: SDLCState) -> ValidatorResult:
    rule = _RULE_SETS.get(name)
    if rule is None:
        return ValidatorResult(
            passed=False,
            flags=[
                _flag(
                    phase,
                    flag_type="tool_error",
                    severity="error",
                    detail=(
                        f"unknown or unimplemented rule_set {name!r}; "
                        "fail-closed (reserved names wait for their owning section)"
                    ),
                )
            ],
            gaps=[f"rule_set {name!r} is not registered"],
        )
    outcome = rule(state)
    if hasattr(outcome, "__await__"):
        outcome = await outcome  # type: ignore[misc]
    return outcome


async def _on_failure(
    config: Validator,
    store: HitlStore,
    state: SDLCState,
    result: ValidatorResult,
) -> dict:
    flags = list(result.flags) or [
        _flag(
            config.phase,
            flag_type="spec_inconsistency",
            severity="error",
            detail=f"validator {config.rule_set!r} failed",
        )
    ]
    report = {
        # Structured "what to fix" for the producing agent. Not a bare "try again".
        "loop_id": f"{config.phase}_validator_to_{config.independent_of}",
        "failed_agent": config.independent_of,
        "failure_type": "validator_rejected",
        "validator_findings": list(result.findings) or [dict(flag) for flag in flags],
        "specific_gaps": list(result.gaps) or [flag["detail"] for flag in flags],
        "suggested_approach": None,
        "attempt_number": int(state.get("rollback_count") or 0) + 1,
    }
    updates: dict[str, Any] = {
        "validation_flags": flags,
        "feedback_reports": [report],
        "agent_events": [_event(state, config, f"validator_failed_{config.on_failure}", result)],
    }
    if config.on_failure == "feedback_loop":
        return updates
    if config.on_failure == "suspend":
        # We only mark it. Phase 10's global rollback cap is what actually stops the task.
        updates["current_rollback_target"] = config.independent_of
        return updates
    # Ask a human. Not an ApprovalGate checkpoint — request_type is risk_approval.
    return await _hitl_failure(config, store, state, result, updates)


async def _hitl_failure(
    config: Validator,
    store: HitlStore,
    state: SDLCState,
    result: ValidatorResult,
    updates: dict[str, Any],
) -> dict:
    checkpoint = f"validator-{config.phase}"
    existing = await store.get_open(task_id=state["task_id"], checkpoint=checkpoint)
    if existing is None:
        request_id = str(uuid4())
        existing = await store.insert_open(
            {
                "request_id": request_id,
                "task_id": state["task_id"],
                "request_type": "risk_approval",
                "phase": config.phase,
                "reason": f"validator {config.rule_set} failed",
                "evidence_ref": f"hitl://{state['task_id']}/{checkpoint}/{request_id}",
                "options": ["acknowledge", "reject_with_feedback"],
                "checkpoint": checkpoint,
                "timeout_at": utcnow() + timedelta(minutes=config.timeout_minutes),
            }
        )
    decision = interrupt_with_span(
        state["task_id"],
        {
            "request_id": existing["request_id"],
            "request_type": "risk_approval",
            "phase": config.phase,
            "reason": existing["reason"],
            "options": existing["options"],
            "gaps": result.gaps,
        },
        name=f"validator_{config.phase}",
        phase=config.phase,
        sink=config.sink,
    )
    now = utcnow()
    await store.mark_responded(
        existing["request_id"],
        response=str(decision),
        responded_by="human",
        responded_at=now,
    )
    updates["hitl_queue"] = [
        item
        for item in (state.get("hitl_queue") or [])
        if item.get("request_id") != existing["request_id"]
    ]
    updates["hitl_history"] = [
        {
            "request_id": existing["request_id"],
            "request_type": "risk_approval",
            "phase": config.phase,
            "reason": existing["reason"],
            "evidence_ref": existing["evidence_ref"],
            "options": list(existing["options"]),
            "response": str(decision),
            "responded_by": "human",
            "responded_at": now,
            "timeout_at": existing["timeout_at"],
        }
    ]
    return updates


def _flag(
    phase: str,
    *,
    flag_type: str,
    severity: str,
    detail: str,
) -> ValidationFlag:
    return {
        "source": "validator",
        "agent_id": "validator",
        "phase": phase,
        "flag_type": flag_type,  # type: ignore[typeddict-item]
        "severity": severity,  # type: ignore[typeddict-item]
        "detail": detail,
        "rollback_to": None,
    }


def _event(state: SDLCState, config: Validator, event_type: str, result: ValidatorResult) -> dict:
    return {
        "event_id": uuid4().hex,
        "task_id": state["task_id"],
        "timestamp": utcnow().isoformat(),
        "agent_id": f"validator:{config.phase}",
        "phase": config.phase,
        "span_id": None,
        "parent_span_id": None,
        "event_type": event_type,
        "payload": {
            "rule_set": config.rule_set,
            "independent_of": config.independent_of,
            "passed": result.passed,
            "gaps": result.gaps,
            "on_failure": config.on_failure,
        },
    }
