# Section 01 — Automated Scoring Pipeline & KPI Store

## Objective

Implement `EvaluationPipeline.score(task_id)` as an ARQ job: hydrate a `RunRecord` via `packages/evaluation/loaders/postgres.py`, call `EvaluationEngine` (§L.6), persist Task-Level KPIs to `evaluation_results` and per-metric rows to `evaluation_scores` (§R), within 60 seconds.

## Why It Exists

This is the mechanism that turns the KPI tables in §L.2 from documentation into live numbers, and is the prerequisite for every other section in this phase and for recalibration work flagged as "future" throughout Phases 04–12.

## Dependencies

Phase 00 (`cost_tracking`; `evaluation_results` / `evaluation_scores` migrations may land here or in Section 05). **Build Section 04's `EvaluationEngine` skeleton in the same sitting** — this section is the job trigger, not a parallel formula pile.

## Atomic Implementation Tasks

1. Implement deterministic evaluators for §L.1 Task-Level KPIs against `cost_tracking`, `hitl_log`, `Task.state`, `rollback_count`.
2. Implement Attribution Accuracy using `feedback_loop_events` (Phase 10 §04). Do not parse LangGraph checkpoints.
3. Wire `EvaluationPipeline.score()` as an ARQ job on task completion (60s SLA).
4. Persist `evaluation_results` plus one `evaluation_scores` row per `metric_id`.
5. Grep: `packages/evaluation/` contains no `langgraph` import.
6. Test: complete a demo task; KPIs match hand calculation.

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
