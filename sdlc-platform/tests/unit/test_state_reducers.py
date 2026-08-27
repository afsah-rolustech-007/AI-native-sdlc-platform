"""Reducer unit tests for SDLCState (§B.2)."""

from typing import get_args, get_type_hints

from langgraph.graph.message import add_messages
from tests.factories import make_task

from orchestration.state import (
    SDLCState,
    TaskDecomposition,
    append_only,
    initial_sdlc_state,
)


def test_append_only_accumulates_instead_of_replacing() -> None:
    first = append_only([], [{"id": "a"}])
    second = append_only(first, [{"id": "b"}])
    assert second == [{"id": "a"}, {"id": "b"}]
    assert append_only(["keep"], ["add"]) != ["add"]


def test_add_messages_accumulates_human_transcript() -> None:
    first = add_messages([], [{"role": "user", "content": "please add login"}])
    second = add_messages(first, [{"role": "user", "content": "approved"}])
    assert len(second) == 2
    assert second[0].content == "please add login"
    assert second[1].content == "approved"


def test_sdlc_state_annotations_use_append_only_and_add_messages() -> None:
    hints = get_type_hints(SDLCState, include_extras=True)
    assert append_only in get_args(hints["agent_events"])
    assert append_only in get_args(hints["worker_coordination_packets"])
    assert append_only in get_args(hints["clarification_escalations"])
    assert append_only in get_args(hints["topology_decisions"])
    assert append_only in get_args(hints["wave_handoff_notes"])
    assert add_messages in get_args(hints["messages"])
    # Replace-semantics: no reducer on the current plan.
    assert get_args(hints["execution_plan"]) == () or append_only not in get_args(
        hints["execution_plan"]
    )


def test_task_decomposition_has_no_execution_order() -> None:
    assert "execution_order" not in TaskDecomposition.__annotations__


def test_initial_state_is_empty_except_identity() -> None:
    task = make_task(id="task-state-1")
    state = initial_sdlc_state(task)
    assert state["task_id"] == "task-state-1"
    assert state["agent_events"] == []
    assert state["current_wave_index"] == -1
    assert state["requirements"] is None
    assert "task_state" not in state
