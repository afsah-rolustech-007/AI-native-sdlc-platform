# Section 03 — Review Manager

## Objective

Implement the Review Manager (§E.8: coordinates diff review against design + standards), replacing Phase 01's stub `review_node`.

## Why It Exists

QA (Phase 07) verifies correctness and spec compliance; Review verifies the diff is *well-formed* against the design and coding standards — a genuinely different lens (style, architectural fit, maintainability) that QA's tools don't cover.

**Merge and conflict handling is not part of Review.** All overlap detection, merge eligibility, serialize-and-rerun, and replan triggering belong exclusively to Phase 06 §06's **Fan-in Coordinator** (§D.4.1) — a deterministic graph node, not an agent. There is no Merge Conflict Resolver agent anywhere in the architecture. Review receives an already fan-in-merged diff; it does not re-resolve conflicts.

## Expected Architecture

`packages/agents/release/review_manager.py`'s `ReviewManager(BaseAgent)` (High-capability tier, §E.8) compares the final merged diff against `ArchitectureDoc` (Phase 06) and a coding-standards checker (reuses Semgrep/ruff from Phase 06 §07 for style-standard enforcement, distinct from `Validator`(implementation)'s correctness-focused checks), producing a review outcome (`approved | changes_requested`). On `changes_requested`, routes back to Implementation (§D.3's Review row) with a structured `FeedbackReport`.

The canonical implementation flow (§D.4.0):

```
Implementation Manager
  → [Send] CodeGen × N (parallel, isolated worktrees)
       each branch: CodeGen → Validator(implementation) [per-branch, tool-only]
  → Fan-in Coordinator → Integration Validator
```

Review sits **after** QA on the merged artifact — it never intercepts merge/conflict decisions.

## Dependencies

Phase 07 (QA-passed diff), Phase 06 (`ArchitectureDoc` to review against; fan-in-complete merged diff).

## Atomic Implementation Tasks

1. Implement `ReviewManager`'s comparison logic: diff vs. `ArchitectureDoc`'s component boundaries/contracts, plus a style/standards pass.
2. Implement the `changes_requested` routing back to Implementation, with a structured `FeedbackReport`.
3. Implement the real `review` graph node replacing Phase 01's stub.
4. Integration test: the demo feature passes Review cleanly; a deliberately design-inconsistent diff (e.g., an API contract violation) is caught and routed to `changes_requested`.

## Manual Testing Procedure

1. Run the demo feature through Review and confirm a clean `approved` outcome.
2. Introduce a deliberate design inconsistency into the diff and confirm Review correctly flags it and routes back to Implementation.

## Expected Demo

Terminal walkthrough of a clean review pass and a caught design-inconsistency case, side by side.

## Acceptance Criteria

- [ ] Review Manager correctly distinguishes `approved` from `changes_requested` for both a clean and a deliberately flawed diff.
- [ ] Review node does not implement merge/conflict logic — no overlap detection, no diff reconciliation, no LLM merge calls (grep-verifiable absence of merge-resolution code in this package).
- [ ] The real `review` node replaces Phase 01's stub.

## Risks

- **Risk:** A conflict reaching Review means Fan-in Coordinator failed upstream — treat as a Phase 06 §06 bug, not something Review should silently absorb. **Mitigation:** Review assumes fan-in output is merge-clean; log/alert if incoming diff metadata indicates unresolved conflict flags.

## Future Improvements

- Richer standards checking once real review patterns accumulate.

## Research Opportunities

None yet.
