"""Validator template: pluggable rules, feedback_loop routing, independent_of."""

from __future__ import annotations

from tests.factories import make_task

from agents.templates.validator import (
    RESERVED_RULE_SETS,
    Validator,
    ValidatorResult,
    build_validator_node,
    register_rule_set,
    unregister_rule_set,
)
from model_adapters.base import ChatMessage, ModelRequest
from orchestration.state import SDLCState, initial_sdlc_state

PRODUCER_CACHE = {"model_response": {"text": "producer output — must not leak"}}


def _state() -> SDLCState:
    return initial_sdlc_state(make_task(id="task-validator-1"))


def _pass(_state: SDLCState) -> ValidatorResult:
    return ValidatorResult(passed=True)


def _fail(state: SDLCState) -> ValidatorResult:
    return ValidatorResult(
        passed=False,
        flags=[
            {
                "source": "validator",
                "agent_id": "validator",
                "phase": "requirements",
                "flag_type": "spec_inconsistency",
                "severity": "error",
                "detail": "acceptance criteria are empty",
                "rollback_to": None,
            }
        ],
        gaps=["acceptance criteria are empty"],
        findings=[{"code": "empty_ac"}],
    )


def _fresh_context_rule(state: SDLCState) -> ValidatorResult:
    # New ModelRequest each call — not a cached reference to the producer.
    request = ModelRequest(
        messages=[ChatMessage(role="user", content="validator-only context")],
        task_id=state["task_id"],
        phase="requirements",
        agent_id="validator",
        operation="consistency-check",
    )
    assert request.messages[0].content != PRODUCER_CACHE["model_response"]["text"]
    assert "model_response" not in state
    return ValidatorResult(passed=True)


async def test_validator_passes_through_on_success() -> None:
    register_rule_set("always_pass", _pass)
    try:
        node = Validator(
            phase="requirements",
            rule_set="always_pass",
            independent_of="requirements_analyst",
            on_failure="feedback_loop",
        ).as_node()
        updates = await node(_state())
        assert updates["agent_events"][0]["event_type"] == "validator_passed"
        assert "validation_flags" not in updates
        assert "feedback_reports" not in updates
    finally:
        unregister_rule_set("always_pass")


async def test_validator_failure_routes_to_feedback_loop() -> None:
    register_rule_set("always_fail", _fail)
    try:
        node = build_validator_node(
            Validator(
                phase="requirements",
                rule_set="always_fail",
                independent_of="requirements_analyst",
                on_failure="feedback_loop",
            )
        )
        updates = await node(_state())
        assert updates["validation_flags"][0]["flag_type"] == "spec_inconsistency"
        report = updates["feedback_reports"][0]
        assert report["failed_agent"] == "requirements_analyst"
        assert "acceptance criteria" in report["specific_gaps"][0]
        assert report["loop_id"] == "requirements_validator_to_requirements_analyst"
        assert updates["agent_events"][0]["event_type"] == "validator_failed_feedback_loop"
    finally:
        unregister_rule_set("always_fail")


async def test_independent_of_uses_fresh_model_request() -> None:
    register_rule_set("fresh_context", _fresh_context_rule)
    try:
        node = Validator(
            phase="requirements",
            rule_set="fresh_context",
            independent_of="echo",
            on_failure="feedback_loop",
        ).as_node()
        updates = await node(_state())
        assert updates["agent_events"][0]["payload"]["independent_of"] == "echo"
        assert updates["agent_events"][0]["payload"]["passed"] is True
    finally:
        unregister_rule_set("fresh_context")


async def test_unregistered_rule_set_fails_closed() -> None:
    node = Validator(
        phase="requirements",
        rule_set="consistency-checker",
        independent_of="requirements_analyst",
        on_failure="feedback_loop",
    ).as_node()
    updates = await node(_state())
    assert updates["validation_flags"][0]["flag_type"] == "tool_error"
    assert "consistency-checker" in RESERVED_RULE_SETS


def test_one_validator_class_for_requirements_phase() -> None:
    first = Validator(
        phase="requirements",
        rule_set="always_pass",
        independent_of="requirements_analyst",
    )
    second = Validator(
        phase="requirements",
        rule_set="always_fail",
        independent_of="requirements_analyst",
    )
    assert type(first) is type(second) is Validator
    assert first.phase == second.phase
