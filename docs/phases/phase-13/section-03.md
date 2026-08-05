# Section 03 — Regression Test Generation & Full Evidence Bundle

## Objective

Implement regression test generation (§K.4: after every passing QA, generate tests targeting bugs found and exploratory edge cases, tagged with metadata) and extend Phase 08 §02's evidence bundle to include this phase's new findings (mutation score, security findings, performance results).

## Why It Exists

Phase 07 §04 already commits a regression test from bug reproduction cases; this section generalizes that to *any* QA finding worth locking in as a permanent test, and closes the loop on the evidence bundle standard so a human approver at Phase 08's gates sees the full picture, not just the Phase 07-era subset.

## Dependencies

Sections 01–02 (new finding types to generate tests from and report), Phase 08 §02 (evidence bundle to extend).

## Atomic Implementation Tasks

1. Implement post-QA regression test generation from bug fixes and exploratory findings, committed as pytest fixtures with `{test_id, covers_requirement_id, covers_module, generated_by_task_id}` metadata, feeding `regression_history`.
2. Extend `EvidenceBundle` (Phase 08 §02) with mutation score, security findings breakdown, and performance results.
3. Test: a task with a security finding and a mutation score produces a complete evidence bundle at `ApprovalGate`(pr) reflecting both.

## Manual Testing Procedure

Run a High-risk demo task through full QA and inspect the evidence bundle at approval time for completeness against §K.5's full field list.

## Expected Demo

Printed evidence bundle for a High-risk task showing every §K.5 field populated with real data, plus a newly generated regression test committed to the suite.

## Acceptance Criteria

- [ ] Regression tests are generated and committed with correct metadata for both bug fixes and exploratory findings.
- [ ] `EvidenceBundle` includes all §K.5 fields, fully populated for High-risk tasks.

## Risks

Generated regression tests carry the same tautology risk flagged in Phase 07 §03 — apply the same quality bar (derive expectations independently, not from re-running the implementation).

## Future Improvements

None planned beyond what Phase 15's evaluation reveals is needed.
