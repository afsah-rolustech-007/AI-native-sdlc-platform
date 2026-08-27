"""Stub graph topology: eight sequential phase nodes with a design interrupt."""

from langgraph.checkpoint.memory import InMemorySaver
from tests.factories import make_task

from common.telemetry import NoOpTelemetrySink, RecordingTelemetrySink
from orchestration.dag_constructor import PHASE_ORDER, build_graph
from orchestration.runtime import is_interrupted, run_to_completion, start_or_continue


def _phase_names(snapshot) -> list[str]:
    return [
        event["phase"]
        for event in snapshot.values["agent_events"]
        if event["event_type"] == "phase_completed"
    ]


async def test_stub_graph_pauses_then_traverses_eight_phases_in_order() -> None:
    sink = RecordingTelemetrySink()
    graph = build_graph(
        checkpointer=InMemorySaver(),
        persist_task_state=False,
        sink=sink,
    )
    task = make_task(id="task-graph-1")
    paused = await start_or_continue(graph, task)
    assert is_interrupted(paused)
    assert "design" in tuple(paused.next or ())
    snapshot = await run_to_completion(graph, task, decision="approve")
    assert _phase_names(snapshot) == list(PHASE_ORDER)
    hitl = [
        event
        for event in snapshot.values["agent_events"]
        if event["event_type"] == "hitl_responded"
    ]
    assert hitl[0]["payload"]["decision"] == "approve"
    assert snapshot.values["architecture"]["deployment_strategy"] == "stub"
    assert [span["kind"] for span in sink.started if span["kind"] == "hitl"]


async def test_graph_nodes_do_not_need_postgres() -> None:
    graph = build_graph(
        checkpointer=InMemorySaver(),
        persist_task_state=False,
        sink=NoOpTelemetrySink(),
    )
    task = make_task(id="task-graph-2")
    snapshot = await run_to_completion(graph, task, decision="approve")
    assert _phase_names(snapshot) == list(PHASE_ORDER)
