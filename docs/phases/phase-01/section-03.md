# Section 03 — Interrupt / Resume Round-Trip

## Objective

Insert a single `interrupt()` call into the stub `design_node` (standing in for a future real `ApprovalGate`, per §D.7) and prove the full pause → external decision → `Command(resume=...)` round-trip works correctly against the durable checkpointer from Section 02.

## Why It Exists

Human-in-the-loop approval is a first-class, safety-critical mechanism (Principle 4, §D.7) — not a bolt-on. Every `ApprovalGate` instance from Phase 05 onward is built on exactly this mechanism. Proving it here, with a trivial stub node, isolates any LangGraph interrupt-semantics learning curve from the complexity of a real agent decision, and gives a template every later `ApprovalGate` config copies.

## Expected Architecture

The `design_node` stub calls `interrupt({"reason": "demo approval checkpoint", "options": ["approve", "reject"]})`, which pauses graph execution and persists the paused state via the checkpointer. A separate process/script (`scripts/resume_task.py`) calls `graph.invoke(Command(resume="approve"), config={"configurable": {"thread_id": ...}})` to continue execution from exactly that point.

## Dependencies

Section 02 (durable checkpointing — resume must survive a real process boundary, not just an in-memory pause).

## Atomic Implementation Tasks

1. Add `interrupt()` call inside the stub `design_node`, with a payload shape resembling (but not yet identical to) the future `HITLRequest` TypedDict from §B.2 — close enough to be a realistic rehearsal, not required to be final.
2. Implement `scripts/resume_task.py`: given a `task_id`, fetches current graph state, prints the pending interrupt payload, accepts a decision via CLI arg, and issues `Command(resume=decision)`.
3. Confirm graph execution halts at `interrupt()` and `graph.get_state(config).next` shows the `design_node` (or its interrupt point) as the pending step.
4. Confirm `Command(resume=...)` continues execution past the interrupt and the remaining stub nodes complete normally.
5. Test the "reject" path too — confirm the stub node can branch on the resume value (even trivially, e.g., logging a different event) to prove resume values are actually usable by node logic, not just accepted and ignored.
6. Wrap `interrupt()` with a `kind="hitl"` span: start on pause, end on resume (§B.8.5). Duration is wall-clock wait. Do not fail the task if the sink errors.

## Manual Testing Procedure

1. Start a task run via a script; watch it halt before `design_node` completes.
2. In a separate terminal, run `scripts/resume_task.py <task_id> approve`.
3. Confirm the original graph run (or a subsequent `.invoke()` against the same `thread_id`) completes through to `monitoring`.
4. Repeat with `reject` and confirm the differing behavior is visible in `agent_events`.

## Expected Demo

Two-terminal recording: terminal A shows the task pausing with the interrupt payload printed; terminal B runs the resume script; terminal A (or a follow-up state fetch) shows the task completing.

## Acceptance Criteria

- [ ] Graph execution reliably halts at the `interrupt()` call and this is observable via `graph.get_state(...).next`.
- [ ] `Command(resume=...)` correctly continues execution from the interrupt point, not from the beginning.
- [ ] Both "approve" and "reject" resume values produce observably different downstream behavior.
- [ ] The round-trip works across a process boundary (resume issued from a different process than the one that hit the interrupt) — this is the realistic production shape.

## Risks

- **Risk:** Confusing LangGraph's `interrupt()` (execution-pause primitive) with an application-level `HITLRequest` object (data record of a pending question) is an easy source of bugs — they are related but distinct: `interrupt()` is *how* the graph pauses, `HITLRequest`/`hitl_log` (Phase 00's schema) is *what gets shown to a human and audited*. **Mitigation:** keep this distinction explicit in code comments/docs now, before `ApprovalGate` (Phase 05) has to properly bridge the two.

## Future Improvements

- Timeout-driven auto-escalation on an un-answered interrupt (Fail-Closed: timeout → escalate, never auto-approve, per §E.1's `ApprovalGate` spec) — Phase 08, once real `ApprovalGate` instances exist with real timeout semantics.

## Research Opportunities

None.
