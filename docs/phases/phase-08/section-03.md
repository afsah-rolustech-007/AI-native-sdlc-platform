# Section 03 — Review Manager & Merge Conflict Resolver

## Objective

Implement the Review Manager (§E.8: coordinates diff review against design + standards) and Merge Conflict Resolver (handles overlapping-branch conflicts from fan-in, as a review-time safety net beyond Phase 06 §06's implementation-time detection), replacing Phase 01's stub `review_node`.

## Why It Exists

QA (Phase 07) verifies correctness and spec compliance; Review verifies the diff is *well-formed* against the design and coding standards — a genuinely different lens (style, architectural fit, maintainability) that QA's tools don't cover. The Merge Conflict Resolver exists here as well because, between QA and Review, enough time/state may have passed (especially once Phase 09's UI introduces human-paced review) that a fresh conflict check before merge is worthwhile insurance beyond Phase 06's fan-in check.

## Expected Architecture

`packages/agents/release/review_manager.py`'s `ReviewManager(BaseAgent)` (High-capability tier, §E.8) compares the final diff against `ArchitectureDoc` (Phase 06) and a coding-standards checker (reuses Semgrep/ruff from Phase 06 §07 for style-standard enforcement, distinct from `Validator`(implementation)'s correctness-focused checks), producing a review outcome (`approved | changes_requested`). On `changes_requested`, routes back to Implementation (§D.3's Review row) with a structured `FeedbackReport`. `MergeConflictResolver` runs just before merge, re-checking file overlaps against the current state of the target branch (which may have moved since Phase 06's fan-in check, especially if multiple tasks run concurrently against the same repo) — on conflict, resolves trivial conflicts automatically or schedules a serialized re-run; on non-trivial conflict, escalates to HITL.

## Dependencies

Phase 07 (QA-passed diff), Phase 06 (`ArchitectureDoc` to review against).

## Atomic Implementation Tasks

1. Implement `ReviewManager`'s comparison logic: diff vs. `ArchitectureDoc`'s component boundaries/contracts, plus a style/standards pass.
2. Implement the `changes_requested` routing back to Implementation, with a structured `FeedbackReport`.
3. Implement `MergeConflictResolver`'s re-check against the current target-branch state (this only becomes meaningfully different from Phase 06 §06's check once multiple concurrent tasks against the same repo are actually exercised — write the check generically now, and note that its real value is proven once Phase 08's demo or later phases run genuinely concurrent tasks).
4. Implement the real `review` graph node replacing Phase 01's stub.
5. Integration test: the demo feature passes Review cleanly; a deliberately design-inconsistent diff (e.g., an API contract violation) is caught and routed to `changes_requested`.

## Manual Testing Procedure

1. Run the demo feature through Review and confirm a clean `approved` outcome.
2. Introduce a deliberate design inconsistency into the diff and confirm Review correctly flags it and routes back to Implementation.
3. If feasible, simulate two concurrent tasks touching overlapping files reaching Review around the same time, and confirm the Merge Conflict Resolver catches the late-stage overlap.

## Expected Demo

Terminal walkthrough of a clean review pass and a caught design-inconsistency case, side by side.

## Acceptance Criteria

- [ ] Review Manager correctly distinguishes `approved` from `changes_requested` for both a clean and a deliberately flawed diff.
- [ ] Merge Conflict Resolver correctly re-checks against current target-branch state before merge, not just relying on Phase 06's earlier check.
- [ ] The real `review` node replaces Phase 01's stub.

## Risks

- **Risk:** Late-stage conflict detection (this section) discovering a conflict that Phase 06's fan-in should have caught earlier indicates a gap in that earlier check, not just a "second layer of defense working as intended." **Mitigation:** if this section's resolver fires non-trivially often, treat it as a signal to revisit Phase 06 §06's detection window/timing, not just something to keep silently absorbing here.

## Future Improvements

- Automatic resolution of genuinely trivial conflicts (e.g., non-overlapping hunks in the same file) — a reasonable enhancement once real conflict patterns are observed.

## Research Opportunities

None yet.
