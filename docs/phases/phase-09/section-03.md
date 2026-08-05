# Section 03 — Workflow Overview & SDLC Phase View (3, 4)

## Objective

Build Screen 3 (Workflow Overview — the `WorkflowProfile` in plain language: risk tier, methodology, active agents, and *which §F.3 rule fired*) and Screen 4 (SDLC Phase View — current position in the §D.3 state machine, with backward edges shown as visually distinct loops).

## Why It Exists

These screens make the platform's *decisions* legible, not just its outputs — directly serving the roadmap's repeated emphasis on deterministic, auditable routing (Principle 5). Screen 3 in particular is only fully meaningful once Phase 10 exists (until then, every task uses the same conservative default profile, and the screen should say so plainly rather than fabricating rule-firing detail that doesn't exist yet) — build the screen now against whatever routing info is currently real, and note explicitly that its full value unlocks once Phase 10 lands.

## Expected Architecture

Screen 3 reads `Task.workflow_profile_id` and (currently) the fail-closed default profile's fixed contents, rendering "why" as "conservative default — real rule-based routing lands in a later phase" until Phase 10 exists, then automatically becomes accurate once Phase 10 populates real rule-firing metadata. Screen 4 reads `SDLCState.state`/`TaskState` history (derived from `agent_events`, Phase 00 §05) and renders the phase sequence as a graph/timeline, with any backward transitions (feedback loops, Phase 06+) rendered as a visually distinct "loop back" indicator rather than a plain forward step.

## Dependencies

Section 01 (client plumbing), Phase 05–08 (real phase transitions and feedback loops to visualize).

## Atomic Implementation Tasks

1. Implement `GET /tasks/{id}/workflow-profile` returning the current profile plus (once it exists) the specific rule that fired; return an explicit "default/no rule engine yet" indicator until Phase 10.
2. Build Screen 3's UI: risk tier, methodology, active agent list, and the rule-firing explanation (or its placeholder).
3. Implement `GET /tasks/{id}/phase-history` deriving an ordered list of phase transitions (including backward ones) from `agent_events`.
4. Build Screen 4's UI: a horizontal/vertical phase-sequence visualization, with backward transitions rendered distinctly (e.g., a different color/arrow style) — reflecting §D.3's explicit statement that backward edges are "explicit, not implicit."
5. Integration test: render Screen 4 for a task that went through at least one real feedback loop (e.g., a forced `FL-04` from Phase 06 §07) and confirm the loop-back is visually distinguishable from forward progress.

## Manual Testing Procedure

1. Run a task with no feedback loops and confirm Screen 4 shows a clean forward sequence.
2. Run a task with a forced feedback loop (reuse a Phase 06/07 forced-failure scenario) and confirm Screen 4 clearly shows the backward transition.
3. Confirm Screen 3 accurately reflects the current (pre-Phase-10) default-profile state without overstating rule-based reasoning that doesn't exist yet.

## Expected Demo

Screenshots of Screen 3 and Screen 4 for both a clean-path task and a task that hit a real feedback loop, showing the loop visually distinct on Screen 4.

## Acceptance Criteria

- [ ] Screen 3 accurately represents the current routing state, including honestly indicating the pre-Phase-10 default-profile limitation rather than fabricating detail.
- [ ] Screen 4 correctly renders both forward and backward phase transitions, with backward transitions visually distinct.
- [ ] Both screens update live as a task progresses, via Section 01's WebSocket plumbing.

## Risks

- **Risk:** Building Screen 3 against a not-yet-real routing engine risks the screen needing rework once Phase 10 lands. **Mitigation:** design the data contract (`GET /tasks/{id}/workflow-profile`'s response shape) to already include the "rule fired" field now (populated with a placeholder value), so Phase 10 only needs to populate real data into an existing contract, not change the contract itself.

## Future Improvements

- Full rule-firing transparency — automatically improves once Phase 10 exists, with zero UI code changes needed if the data contract is designed correctly now.

## Research Opportunities

None.
