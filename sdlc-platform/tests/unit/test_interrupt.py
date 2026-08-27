"""Design interrupt / Command(resume=...) round-trip."""

from langgraph.checkpoint.memory import InMemorySaver
from tests.factories import make_task

from common.telemetry import NoOpTelemetrySink, RecordingTelemetrySink
from orchestration.dag_constructor import PHASE_ORDER, build_graph
from orchestration.hitl import DESIGN_APPROVAL_PAYLOAD
from orchestration.runtime import interrupt_value, is_complete, resume_graph, start_or_continue


async def test_interrupt_payload_resembles_hitl_request() -> None:
    graph = build_graph(
        checkpointer=InMemorySaver(),
        persist_task_state=False,
        sink=NoOpTelemetrySink(),
    )
    task = make_task(id="task-hitl-payload")
    paused = await start_or_continue(graph, task)
    payload = interrupt_value(paused)
    assert payload["reason"] == DESIGN_APPROVAL_PAYLOAD["reason"]
    assert payload["options"] == ["approve", "reject"]
    assert payload["request_type"] == "approval"
    assert not is_complete(paused)


async def test_approve_and_reject_leave_different_events() -> None:
    async def _run(task_id: str, decision: str):
        graph = build_graph(
            checkpointer=InMemorySaver(),
            persist_task_state=False,
            sink=RecordingTelemetrySink(),
        )
        task = make_task(id=task_id)
        await start_or_continue(graph, task)
        return await resume_graph(graph, task, decision)

    approved = await _run("task-hitl-approve", "approve")
    rejected = await _run("task-hitl-reject", "reject")
    assert is_complete(approved) and is_complete(rejected)
    approve_hitl = [
        e["payload"]["decision"]
        for e in approved.values["agent_events"]
        if e["event_type"] == "hitl_responded"
    ]
    reject_hitl = [
        e["payload"]["decision"]
        for e in rejected.values["agent_events"]
        if e["event_type"] == "hitl_responded"
    ]
    assert approve_hitl == ["approve"]
    assert reject_hitl == ["reject"]
    assert approved.values["architecture"]["deployment_strategy"] == "stub"
    assert rejected.values["architecture"]["deployment_strategy"] == "rejected-stub"
    approve_phases = [
        e["phase"] for e in approved.values["agent_events"] if e["event_type"] == "phase_completed"
    ]
    assert approve_phases == list(PHASE_ORDER)


async def test_hitl_span_starts_on_pause_and_ends_on_resume() -> None:
    sink = RecordingTelemetrySink()
    graph = build_graph(
        checkpointer=InMemorySaver(),
        persist_task_state=False,
        sink=sink,
    )
    task = make_task(id="task-hitl-span")
    await start_or_continue(graph, task)
    hitl_ids = [span["span_id"] for span in sink.started if span["kind"] == "hitl"]
    assert hitl_ids
    assert hitl_ids[0] not in {item["span_id"] for item in sink.ended}
    await resume_graph(graph, task, "approve")
    assert hitl_ids[0] in {item["span_id"] for item in sink.ended}
