# Section 06 — QA Summary, Deployment Status & Final Report (10, 11, 12)

## Objective

Build Screen 10 (QA Summary — which checks ran, results, bug reproduction result first for bug/hotfix), Screen 11 (Deployment Status — strategy, pipeline URL, canary metrics/health comparison, thresholds), and Screen 12 (Final Report — definition-of-done checklist, cost breakdown, HITL history, files changed, ADRs, KPI scores) — completing the 12-screen UI.

## Why It Exists

These are the "did it work, and what did it cost" screens — the natural closing view of a task's lifecycle, pulling together data from Phase 07 (QA), Phase 08 (deployment), Phase 02 (cost), and eventually Phase 15 (KPI scores, populated once that phase exists — Screen 12 should degrform gracefully, showing "not yet available" rather than breaking, until then).

## Expected Architecture

Screen 10 reads `QAEvidence` (Phase 07 §B.2), rendering per-check results per §K.1's matrix (only the "Always" rows are populated until Phase 13 adds the rest — the screen should clearly show which checks ran vs. which are risk-gated and inactive at this phase), with bug reproduction result surfaced first for bug/hotfix work types per §P's explicit instruction. Screen 11 reads `DeploymentRecord` (Phase 08 §05), rendering strategy, pipeline reference, and canary metrics (currently simulated/simplified per Phase 08's provisional deployment simulation — the screen's data contract should already support the richer canary-analysis fields the blueprint's comparative analysis names, even if populated minimally now). Screen 12 assembles a full task retrospective: definition-of-done checklist (derived from `RequirementsSpec.acceptance_criteria` vs. Spec QA's compliance report, Phase 07 §05), cost breakdown (from `cost_tracking`, Phase 00/02), full HITL history (`hitl_log`/`approvals`), files changed (from the diff), ADRs generated (`design_decisions`), and a KPI scores section explicitly marked "pending Phase 15" until that phase exists.

## Dependencies

Phase 07 (`QAEvidence`), Phase 08 (`DeploymentRecord`, HITL history), Phase 02 (cost data).

## Atomic Implementation Tasks

1. Implement `GET /tasks/{id}/qa-summary`, `GET /tasks/{id}/deployment-status`, `GET /tasks/{id}/final-report` endpoints assembling the respective data.
2. Build Screen 10: per-check QA results table, bug reproduction surfaced first when applicable, clear indication of which §K.1 rows are active vs. not-yet-implemented (until Phase 13).
3. Build Screen 11: deployment strategy/status display with a canary metrics section (populated minimally, data contract ready for Phase 08's future real canary-analysis enhancement).
4. Build Screen 12: the full retrospective assembly, with a clearly marked "KPI scores: available from Phase 15" placeholder section.
5. Integration test: render all three screens for a fully completed demo task (the Phase 08 end-to-end demo scenario) and verify every populated field against the underlying database records.

## Manual Testing Procedure

1. Complete a full task through the entire pipeline (Phases 05–08) and view Screens 10, 11, 12 for it.
2. Cross-check every displayed value against the corresponding database row/API response for correctness.
3. Complete a bug/hotfix-type task and confirm Screen 10 correctly surfaces the bug reproduction result first, per §P.

## Expected Demo

This section's demo *is* Phase 09's overall closing demo (see README): the complete UI walkthrough from Screen 1 through Screen 12 for one full task, plus a second walkthrough of Screen 10 specifically for a bug/hotfix task showing the reproduction-result-first ordering.

## Acceptance Criteria

- [ ] Screen 10 correctly displays QA results with bug/hotfix reproduction results surfaced first, and clearly distinguishes active vs. not-yet-implemented checks.
- [ ] Screen 11 correctly displays deployment status and strategy from real (simulated) `DeploymentRecord` data.
- [ ] Screen 12 correctly assembles a complete retrospective from all upstream data sources, with an honest "pending Phase 15" placeholder for KPI scores rather than fabricated numbers.
- [ ] All 12 screens from §P are now implemented, closing out Phase 09's full scope.

## Risks

- **Risk:** A "Final Report" screen that looks complete but silently omits a data source (e.g., forgetting to include scope-creep findings from Phase 07 §05) undermines the report's trustworthiness. **Mitigation:** build Screen 12 as an explicit checklist against every named data source in §P's table, cross-checked item by item during the manual test, rather than assembling it ad hoc.

## Future Improvements

- Real canary-metrics visualization (health comparison chart) — once Phase 08's deployment simulation is replaced with something closer to real canary data.
- KPI scores — Phase 15.

## Research Opportunities

None — Phase 09 closes the UI's initial scope; further UI research (if any) is downstream of what Phase 15's evaluation reveals is actually useful to show.
