"""Parent StateGraph: eight sequential phase stubs (§D.3 forward path).

`design_node` pauses on interrupt(). No conditional edges or subgraphs yet
(Phase 06). Pass `on_node_enter` for the crash-recovery harness (Section 04).

Default nodes stay stubs so Phase 01 topology tests keep pausing at design.
Pass `node_overrides={"intake": build_intake_node(...)}` to compile the real
Planning Manager path (Phase 05 §03) without rewriting this graph.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from itertools import pairwise

from langgraph.graph import END, START, StateGraph

from common.telemetry import TelemetrySink
from orchestration.nodes import STUB_NODES
from orchestration.state import SDLCState
from orchestration.telemetry_adapter import NodeEnterHook, NodeFn, wrap_phase_node

# Exact §D.3 forward path. Node names must stay these strings.
PHASE_ORDER: tuple[str, ...] = (
    "intake",
    "requirements",
    "design",
    "implementation",
    "qa",
    "review",
    "release",
    "monitoring",
)


def build_graph(
    *,
    checkpointer=None,
    persist_task_state: bool = True,
    sink: TelemetrySink | None = None,
    on_node_enter: NodeEnterHook | None = None,
    node_overrides: Mapping[str, Callable] | None = None,
):
    """Compile the eight-phase parent graph.

    Default = Phase 01 stubs (intake is a no-op; pause is still at design).
    To run real Planning Manager, pass node_overrides for `intake` only.
    Node names must stay these strings because wrap_phase_node does TaskState(phase).
    """
    # Start from stubs, then overlay any real nodes (intake today, more later).
    nodes: dict[str, NodeFn] = {**STUB_NODES, **(node_overrides or {})}
    builder = StateGraph(SDLCState)
    for phase in PHASE_ORDER:
        builder.add_node(  # type: ignore[call-overload]
            phase,
            wrap_phase_node(
                phase,
                nodes[phase],
                persist_task_state=persist_task_state,
                sink=sink,
                on_node_enter=on_node_enter,
            ),
        )
    builder.add_edge(START, PHASE_ORDER[0])
    for current, nxt in pairwise(PHASE_ORDER):
        builder.add_edge(current, nxt)
    builder.add_edge(PHASE_ORDER[-1], END)
    return builder.compile(checkpointer=checkpointer)
