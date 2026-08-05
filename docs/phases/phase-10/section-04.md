# Section 04 — Centralized Feedback Loop Registry & Global Rollback Guard

## Objective

Implement the Feedback Loop Registry (§F.5) as a single, centralized, named/parametrized table covering all 11 loops (`FL-01` through `FL-11`) — consolidating loops that were implemented piecemeal across Phases 05–07 (`FL-01`, `FL-02`, `FL-03`, `FL-04`, `FL-05`, `FL-06`, `FL-07`) plus the ones not yet built (`FL-08` security finding, `FL-09` deployment health, `FL-10` MASC critical anomaly, `FL-11` intent contradiction) — and the fully-general global `rollback_count` guard.

## Why It Exists

The blueprint is explicit: "Every loop is named, parametrized, and registered. Not scattered through agent code." Phases 05–07 correctly implemented individual loops' *logic* but did so inline, phase by phase, per `roadmap.md`'s own note that the full registry wasn't formalized until this phase. Centralizing them now — without changing their individual behavior — makes the system's total feedback-loop surface auditable in one place, and is what makes Phase 15's "Feedback Loop Health" KPIs (§L.2) computable at all.

## Expected Architecture

`packages/orchestration/feedback.py`'s `FEEDBACK_LOOP_REGISTRY: dict[str, FeedbackLoopSpec]` implements §F.5's exact table (`loop_id`, `trigger`, `source_agent`, `target_agent`, `max_iterations`, `rollback_depth`, `hitl`) for all 11 loops. Every loop-firing call site across Phases 05–08 (currently direct function calls/routing logic embedded in each `Validator`/MASC/agent) is refactored to go through a single `fire_feedback_loop(loop_id, task_id, context)` function that looks up the spec, enforces `max_iterations`, applies `rollback_depth`, and triggers HITL if specified — this is a genuine refactor of existing code, not new logic. `FL-08` (critical security finding → design phase, HITL) becomes reachable once Phase 13 adds security QA depth, but the registry entry and its plumbing are built now. `FL-09` (deployment health → CI/CD rollback, automated) is wired to Phase 08 §05's Rollback Sub-agent. `FL-10` (MASC critical anomaly → previous checkpoint, HITL) is wired to MASC's existing critical-severity path. `FL-11` (intent contradiction → requirements, HITL) is wired to Phase 05 §06's Intent Tracker, finally activating its previously-stubbed `flag_drift_mid_implementation()` for real, now that Phase 06's implementation phase exists to detect drift during.

## Dependencies

Phases 05–08 (all individually-implemented loops to consolidate), Phase 05 §06 (Intent Tracker's stub to activate), Phase 08 §05 (Rollback Sub-agent), Phase 05 §01 (MASC).

## Atomic Implementation Tasks

1. Implement `FeedbackLoopSpec` and the full `FEEDBACK_LOOP_REGISTRY` table per §F.5.
2. Implement `fire_feedback_loop(loop_id, task_id, context)` as the single entry point for triggering any named loop.
3. Refactor every existing loop-firing call site (Phase 05 §05's `FL-01`, Phase 06 §03's `FL-02`/`FL-03`, Phase 06 §07's `FL-04`, Phase 06 §06's `FL-05`, Phase 07 §03/§05's `FL-06`/`FL-07`) to call `fire_feedback_loop()` instead of their ad hoc inline routing — verify behavior is unchanged via each phase's existing tests.
4. Wire `FL-08` (security finding → design, HITL) into the registry, ready for Phase 13's Security QA to trigger it.
5. Wire `FL-09` (deployment health → automated CI/CD rollback) to Phase 08 §05's `RollbackSubAgent`.
6. Wire `FL-10` (MASC critical anomaly → previous checkpoint, HITL) into MASC's existing critical-severity handling (Phase 05 §01).
7. Activate `FL-11`: implement `IntentTracker.flag_drift_mid_implementation()` (Phase 05 §06's stub) for real — checking new messages received during Phase 06's implementation phase against `SDLCState.requirements`/`intent_version`, firing `FL-11` on detected contradiction.
8. Implement the fully-general global guard: `task.rollback_count >= (max_retries_per_node × active_phases) → suspend task, preserve full state, notify human, block further autonomous execution` (§F.5) — this requires `active_phases` to be derivable from the real `WorkflowProfile` (Section 02), which is why this section depends on Section 02 within the same phase.
9. Integration tests: re-run every phase's existing forced-failure scenarios (Phase 05's `FL-01`, Phase 06's `FL-02`–`FL-05`, Phase 07's `FL-06`/`FL-07`) and confirm identical behavior through the new centralized registry; test `FL-09`, `FL-10`, `FL-11` newly, each with a forced scenario; test the global guard by forcing enough cumulative rollbacks across a task to trigger suspension.

## Manual Testing Procedure

1. Re-run every prior phase's forced-feedback-loop demo scenarios and confirm identical, correct behavior post-refactor.
2. Force a mid-implementation intent contradiction (a new user message reversing an approved requirement, injected during Phase 06's implementation) and confirm `FL-11` correctly fires and routes to Requirements with HITL.
3. Force enough cumulative rollbacks on one task to trigger the global guard and confirm the task suspends cleanly, preserving full state, rather than looping further.

## Expected Demo

This section's demo *is* Phase 10's closing proof: a printed view of the full `FEEDBACK_LOOP_REGISTRY` table alongside a live run exercising at least one previously-existing loop (`FL-04`), one newly-wired loop (`FL-11`), and the global suspension guard — showing the entire safety net operating as one coherent, auditable system rather than scattered logic.

## Acceptance Criteria

- [ ] All 11 named loops exist in one centralized, correctly-specified registry.
- [ ] Every previously-implemented loop (`FL-01` through `FL-07`) behaves identically after refactoring to use the centralized `fire_feedback_loop()` entry point — verified by re-running each phase's original tests.
- [ ] `FL-09`, `FL-10`, and `FL-11` are newly wired and demonstrated working via forced scenarios.
- [ ] The global `rollback_count` guard correctly suspends a task (preserving state, never looping further) once its threshold is breached.

## Risks

- **Risk:** This section's refactor touches code across five prior phases — the single largest "don't break what already works" surface in the roadmap. **Mitigation:** the explicit re-run-existing-tests step is non-negotiable; treat any test failure surfaced by this refactor as a blocking issue to resolve before considering this section (or Phase 10) complete.

## Future Improvements

- Feedback Loop Health KPIs (loop trigger rate, resolution rate, oscillation rate, §L.2) — Phase 15, now finally computable given this section's centralized, uniformly-logged registry.

## Research Opportunities

None directly — but this section is what makes Phase 15's feedback-loop-health research possible at all; treat the quality of this section's logging/instrumentation as directly gating the quality of that future analysis.
