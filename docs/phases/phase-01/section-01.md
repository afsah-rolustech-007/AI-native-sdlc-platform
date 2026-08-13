# Section 01 — SDLCState Schema & Stub Graph Topology

## Objective

Implement the full `SDLCState` TypedDict with all `Annotated` reducers per §B.2, and construct the parent `StateGraph` with one stub node per SDLC phase (§D.3's state machine), wired with plain sequential edges (no conditional routing, no subgraphs yet).

## Why It Exists

`SDLCState` is the shape every future agent reads and writes. Getting the reducers right now (especially `append_only` for events/messages, and the distinction between fields that replace vs. accumulate) prevents subtle state-corruption bugs once parallel fan-out (Phase 06) starts writing concurrently. The stub topology proves the graph *shape* matches §D.3 before any node has real content.

## Expected Architecture

`packages/orchestration/state.py` defines every field from §B.2's `SDLCState`, plus the `RequirementsSpec`, `ArchitectureDoc`, `TaskDecomposition`, `QAEvidence`, `DeploymentRecord`, `ValidationFlag`, `HITLRequest`, `WorkerCoordinationPacket`, `ClarificationEscalation`, and `ReplanContext` sub-TypedDicts — all fields present even though most are `None`/empty until their owning phase populates them. `worker_coordination_packets` and `clarification_escalations` (§D.9.2/§D.9.3) sit empty until Phase 06's fan-out exists, but must be declared correctly now with `append_only` since they are exactly the kind of concurrent-write field this section's reducer discipline exists to protect.

**`messages` scope note (§D.9.1):** this field is the human/system conversation transcript only — HITL responses, user requests, Intent Tracker input. It is never used for agent-to-agent coordination; that traffic lives in `agent_events` (observability only), `worker_coordination_packets`, `clarification_escalations`, and `feedback_reports`. Get this distinction right in the stub now — it's the field most tempting to misuse as a generic "any agent can write here" channel once Phase 06's parallel workers exist. `packages/orchestration/dag_constructor.py` builds a `StateGraph(SDLCState)` with nodes named exactly after §D.3's phases (`intake`, `requirements`, `design`, `implementation`, `qa`, `review`, `release`, `monitoring`), connected by unconditional edges matching the forward path only (backward edges are Phase 06+ concerns, once there's something to roll back from).

## Dependencies

Phase 00 (Task model for `task_id` field).

## Atomic Implementation Tasks

1. Implement `append_only` reducer and every TypedDict from §B.2 verbatim (field names, types, `Annotated` usage).
2. Implement the 8 stub node functions — each takes `SDLCState`, mutates `state[current phase's field]` to a trivial placeholder value, appends one `agent_events` entry via `emit_node_event` (Phase 00 Section 05), and returns the updated state.
3. Build `dag_constructor.py`'s `build_graph()` function returning a compiled `StateGraph` with the 8 nodes in sequence, `intake` as entry point, `monitoring` as terminal.
4. Unit test: compile the graph, run it against a fresh `SDLCState`, assert it traverses all 8 nodes in order and `agent_events` has 8 entries at the end.
5. Unit test: verify `append_only` reducer behavior directly (call it twice, confirm accumulation not replacement) and verify `add_messages` reducer behavior for the `messages` field.

## Manual Testing Procedure

1. Instantiate an initial `SDLCState` for a real `Task` (from Phase 00).
2. Invoke the compiled graph with `.invoke()` (no interrupts yet) and print the final state.
3. Confirm `agent_events` contains exactly 8 entries, one per stub node, in the correct order.

## Expected Demo

Terminal output showing the full final `SDLCState` after a complete stub run, with the `agent_events` list printed showing the 8-node traversal in order.

## Acceptance Criteria

- [ ] `SDLCState` implements every field from §B.2 with correct reducer annotations.
- [ ] The compiled graph traverses all 8 phase-stub nodes in the exact order specified by §D.3's forward path.
- [ ] `append_only` and `add_messages` reducers are independently unit-tested and behave correctly under repeated updates.

## Risks

- **Risk:** Under-specifying a reducer now (e.g., using plain list replacement where `append_only` is needed) silently loses data once parallel writes exist (Phase 06). **Mitigation:** the explicit reducer unit tests in this section exist specifically to catch this before it's a hidden bug three phases later.

## Future Improvements

- Conditional/backward edges — Phase 06 (rollback) and Phase 10 (workflow-profile-driven skip/parallel flags per §D.2).

## Research Opportunities

None.
