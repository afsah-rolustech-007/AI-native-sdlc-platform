# Section 02 — Mutation, Property-Based, Performance & Accessibility QA

## Objective

Wire the remaining risk/condition-gated §K.1 rows: mutation testing (mutmut, risk≥High + critical-path modules only), property-based testing (Hypothesis, risk≥Medium + pure functions), performance QA (k6/Locust, risk≥High + perf-sensitive path), accessibility QA (axe-core, `has_ui_changes`), and API contract fuzzing (schemathesis, `has_api_contract_changes`).

## Why It Exists

These are the remaining deterministic, tool-based checks from §K.1 not yet built — grouped together here because they're independent of each other and share the same pattern (a tool wrapper gated by a `WorkflowContext` condition from Phase 10).

## Dependencies

Phase 10 (conditions to gate on), Phase 07 (QA pipeline to plug into).

## Atomic Implementation Tasks

1. Wire mutmut against critical-path modules only (define "critical-path" pragmatically — e.g., modules flagged `touches_shared_infra`), gated `risk_tier >= High`.
2. Wire Hypothesis for pure functions identified in the diff, gated `risk_tier >= Medium`.
3. Wire k6/Locust for perf-sensitive paths, gated `risk_tier >= High`.
4. Wire axe-core, gated `has_ui_changes`; wire schemathesis, gated `has_api_contract_changes`.
5. Test each gate independently: a task meeting the condition activates the check; a task not meeting it correctly skips.

## Manual Testing Procedure

Run one task per gated condition and confirm correct activation/skip for each of the five checks.

## Expected Demo

A QA plan printout for one High-risk, UI-and-API-changing task showing all five checks active, versus a Low-risk task showing all five skipped.

## Acceptance Criteria

- [ ] Each of the five checks activates/skips correctly per its documented condition.
- [ ] Mutation testing is correctly scoped to critical-path modules only, not the full diff (cost control).

## Risks

Mutation testing is expensive — scope discipline (critical-path only) is the direct mitigation, not something to relax for convenience.

## Future Improvements

Tune "critical-path module" definition based on real usage once enough tasks have run through this gate.
