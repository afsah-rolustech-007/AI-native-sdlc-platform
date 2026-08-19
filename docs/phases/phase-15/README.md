# Phase 15 — Evaluation Framework

## Goal

Measure real platform behavior: a post-task scoring job, an `EvaluationEngine` that scores `RunRecord`s (not LangGraph objects), a golden dataset with shadow-mode graduation, experiment-vs-baseline CI, and DORA metrics.

## Why This Phase Exists

Phases 00–14 generate traces, costs, WCPs, HITL, and QA evidence. This phase is the first consumer that *scores* that evidence. It cannot start earlier as a full system (no volume), but its **interfaces** (`TelemetrySink`, `RunRecord`, `Evaluator`) were specified in §B.8 / §L so instrumentation was not wasted.

## Dependencies

Phases 05–14 for live volume. **Code** depends on Phase 00 telemetry, Phase 02 cost rows, Phase 05+ `feedback_loop_events` / MASC flags, Phase 08 deployments for DORA.

## Expected Live Demo

Complete a task → `EvaluationPipeline.score()` within 60s → `evaluation_results` + `evaluation_scores`. Replay golden dataset; show resolution rate. Break a prompt on a branch; CI blocks on MVP metric regression.

## Deliverables

- `packages/evaluation/engine.py`, `pipeline.py`, `trajectory.py`, `loaders/postgres.py`, `evaluators/`, `experiments.py`.
- `packages/evaluation/benchmarks/golden_dataset.py`, `shadow_mode.py`.
- Grafana dashboard (DORA + KPI trends). **No LangGraph import** in `packages/evaluation/` (grep in CI).

## Sections

1. [Automated Scoring Pipeline & KPI Store](section-01.md)
2. [RunRecord, EvaluationEngine & MVP Evaluators](section-04.md)
3. [Golden Dataset & Shadow-Mode Graduation](section-02.md)
4. [Experiments, Baseline Diff & Self-Evaluation CI](section-05.md)
5. [DORA Metrics & Grafana](section-03.md)

Section 04 is built immediately after Section 01 so later golden/CI work scores through `EvaluationEngine`, not a second ad-hoc formula pile.
