"""Start / continue / resume a stub graph against a checkpointer."""

from __future__ import annotations

from typing import Any

from langgraph.types import Command

from common.task import Task
from orchestration.checkpointers.postgres import get_thread_id
from orchestration.state import initial_sdlc_state


def thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def interrupt_value(snapshot: Any) -> Any | None:
    """Payload passed to interrupt(), or None if the graph is not paused for HITL."""
    interrupts = getattr(snapshot, "interrupts", None) or ()
    if interrupts:
        return getattr(interrupts[0], "value", interrupts[0])
    for task in getattr(snapshot, "tasks", ()) or ():
        nested = getattr(task, "interrupts", ()) or ()
        if nested:
            return getattr(nested[0], "value", nested[0])
    return None


def is_interrupted(snapshot: Any) -> bool:
    return interrupt_value(snapshot) is not None


def is_complete(snapshot: Any) -> bool:
    nxt = tuple(snapshot.next or ())
    return nxt == () and not is_interrupted(snapshot) and bool(snapshot.values)


async def start_or_continue(graph, task: Task) -> Any:
    """Run until interrupt or completion. Does not auto-resume HITL."""
    config = thread_config(get_thread_id(task))
    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        await graph.ainvoke(initial_sdlc_state(task), config)
        return await graph.aget_state(config)
    if is_interrupted(snapshot) or is_complete(snapshot):
        return snapshot
    if snapshot.next:
        await graph.ainvoke(None, config)
        return await graph.aget_state(config)
    return snapshot


async def resume_graph(graph, task: Task, decision: str) -> Any:
    """Issue Command(resume=decision) for this task's thread_id."""
    config = thread_config(get_thread_id(task))
    await graph.ainvoke(Command(resume=decision), config)
    return await graph.aget_state(config)


async def run_to_completion(graph, task: Task, *, decision: str = "approve") -> Any:
    """Full stub run: start, approve/reject the design interrupt, finish."""
    snapshot = await start_or_continue(graph, task)
    if is_interrupted(snapshot):
        snapshot = await resume_graph(graph, task, decision)
    return snapshot
