# Section 04 — Requirements Analyst: Wiring the Questioning Engine into the Graph

## Objective

Implement the Requirements Analyst agent, wiring Phase 04's standalone `QuestioningEngine` into a real graph node that uses real `interrupt()`/`Command(resume=...)` calls (Phase 01 §03) for every human-facing question, replacing Phase 01's stub `requirements_node`.

## Why It Exists

Phase 04 proved the engine's logic works in isolation. This section proves it works embedded in a durable, resumable graph — meaning a multi-round clarification conversation can survive a process restart mid-conversation (directly exercising Phase 01's crash-recovery guarantee under a realistic, not stub, workload).

## Expected Architecture

The `requirements` node runs a loop: call `QuestionQueue.next()`; if a question was auto-answered (Phase 04 §03), continue immediately; if it needs a human, call `interrupt({...question payload...})`; on resume, call `QuestionQueue.answer(...)`; repeat until `QuestionQueue` is exhausted or the exit evaluator (Phase 04 §04) fires. Because this is a *loop* inside one graph node rather than one interrupt per node (unlike Phase 01's single-interrupt stub), this section must handle multiple sequential interrupts within the same node's execution — verify this is a supported LangGraph pattern (looping `interrupt()` calls within one node) and adjust the node/subgraph structure if a different topology (e.g., a dedicated per-question sub-node) is needed.

## Dependencies

Phase 04 (full `QuestioningEngine`), Phase 01 §03 (interrupt/resume), Section 01–02 (BaseAgent, MASC).

## Atomic Implementation Tasks

1. Verify LangGraph's supported pattern for multiple sequential `interrupt()` calls within a single node's execution across resumes (this is a genuine technical unknown worth spiking before committing to a node topology) — document the finding.
2. Implement the `requirements` node per the finding from task 1 — either a looping single node, or a small internal subgraph with one node per question-round.
3. Wire each human-facing `interrupt()` payload to resemble the eventual `HITLRequest` shape (§B.2) more closely than Phase 01's placeholder did, with `request_type="clarification"` set explicitly (not left implicit) — this node is the first real producer of `HITLRequest`-shaped data, feeding Phase 08's `hitl_log` persistence and Phase 09's Screen 2/7.
4. On exit, write the final `RequirementsSpec` (§B.2's TypedDict) into `SDLCState.requirements`, and log `open_ambiguities`/`assumptions` from Phase 04's exit evaluator.
5. Integration test: run a full multi-round requirements session through the real graph (using the vague-request demo scenario from Phase 04), including a mid-session process kill and resume (reusing Phase 01 §04's chaos harness pattern) — assert the session resumes with the correct next question, not from the start.
6. Integration test: run the well-specified demo scenario and confirm it exits quickly via condition (a) without unnecessary interrupts (i.e., auto-answered questions truly don't pause the graph).

## Manual Testing Procedure

1. Start a task with the vague-request scenario; answer 1–2 questions via the resume script; kill the worker process; restart; confirm the next question is exactly the one that should follow, not a repeat or a skip.
2. Run the well-specified scenario end-to-end and time it — it should complete with minimal/no human interrupts, auto-answering nearly everything.
3. Inspect the final `RequirementsSpec` in `SDLCState` for both scenarios for correctness and completeness.

## Expected Demo

This section's demo *is* the core of Phase 05's overall live demo (see README): a multi-round requirements session shown live, including a crash-and-resume mid-conversation, ending in a complete `RequirementsSpec`.

## Acceptance Criteria

- [ ] Multi-round requirements sessions correctly pause/resume across process restarts, with the exact next question preserved (not lost or duplicated).
- [ ] Auto-answered questions genuinely do not trigger a graph pause (verified by trace inspection, not just "it seemed fast").
- [ ] `SDLCState.requirements` is fully and correctly populated at exit, including `open_ambiguities` and `assumptions`.
- [ ] The chosen node/subgraph topology decision is documented, since it's a real technical judgment call made in this section, not dictated verbatim by the blueprint.

## Risks

- **Risk:** LangGraph interrupt semantics within a loop may have edge cases (e.g., state re-entry replaying prior side effects) that aren't obvious until tested against a real multi-round crash scenario. **Mitigation:** this is precisely why the crash-mid-session integration test (task 5) exists — treat any surprising replay behavior discovered here as a documented decision/workaround, not a silent bug.

## Future Improvements

- Full `PhaseHandoffPacket` construction with token budgets — Phase 12; this section writes the raw `RequirementsSpec` but not yet the bounded, summarized handoff packet.

## Research Opportunities

None beyond the LangGraph interrupt-pattern spike itself, which is more "verify library behavior" than open research.
