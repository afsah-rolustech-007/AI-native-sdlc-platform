# Section 01 — Automated Scoring Pipeline & KPI Store

## Objective

Implement `EvaluationPipeline.score(task_id)` (§L.1): on every task completion, compute Fix Rate, Token Efficiency, Cost, HITL Count, Rollback Count, Cycle Time, and Attribution Accuracy in parallel, within 60 seconds, and persist to `evaluation_results` (§R).

## Why It Exists

This is the mechanism that turns the KPI tables in §L.2 from documentation into live numbers, and is the prerequisite for every other section in this phase and for recalibration work flagged as "future" throughout Phases 04–12.

## Dependencies

Phase 00 (`evaluation_results` table), all prior phases (the data each formula reads).

## Atomic Implementation Tasks

1. Implement each formula from §L.1/§L.2's Task-Level table against real data sources already populated by prior phases (`cost_tracking`, `hitl_log`, `SDLCState.rollback_count`, task timestamps).
2. Implement Attribution Accuracy (maps failures to root-cause agent) using the Feedback Loop Registry's logged `source_agent`/`target_agent` data (Phase 10 §04).
3. Wire `EvaluationPipeline.score()` to run as an async ARQ job triggered on task completion, with a 60-second SLA.
4. Implement Phase-Level and Agent-Level KPIs (§L.2) as queries over the same underlying data, not separately tracked state.
5. Test: complete a demo task and confirm all KPIs populate correctly and within the time budget.

## Manual Testing Procedure

Complete a task, wait, and query `evaluation_results` to confirm all fields are populated correctly against hand-calculated expected values.

## Expected Demo

A completed task's full KPI printout within 60 seconds of completion, cross-checked by hand for at least Fix Rate and Cost.

## Acceptance Criteria

- [ ] All Task-Level KPIs from §L.2 compute correctly and within 60 seconds of task completion.
- [ ] Attribution Accuracy correctly identifies the root-cause agent for a task with a known forced failure.

## Risks

Attribution accuracy is inherently approximate for complex multi-agent failure chains — acceptable at v1; treat below-target accuracy as a signal for the Feedback Loop Registry's logging granularity, not a pipeline bug.

## Future Improvements

Real-time KPI dashboards (Grafana) — Section 03.
