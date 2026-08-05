# Phase 15 — Evaluation Framework

## Goal

Measure the platform's real behavior instead of assuming it: an automated post-task scoring pipeline (§L.1), a golden dataset with shadow-mode graduation (§L.3), platform self-evaluation regression suite (§L.4), and DORA metrics (§L.5) — turning every KPI referenced provisionally throughout Phases 00–14 into a real, tracked number.

## Why This Phase Exists

Every prior phase deferred a measurement to "once Phase 15 exists" — confidence-weight recalibration (Phase 04 §04), Feedback Loop Health (Phase 10 §04), context efficiency (Phase 12 §05), retrieval precision tracking (Phase 11 §05). This phase is where those debts are collected into one coherent evaluation system, only possible now that Phases 05–14 have generated enough real, varied task history to measure against.

## Dependencies

Phases 05–14 (real task volume and outcomes to evaluate).

## Expected Live Demo

Complete a task and show `EvaluationPipeline.score()` runs automatically within 60 seconds, populating `evaluation_results`. Show the golden dataset resolution rate as a tracked, trending metric. Show the platform self-evaluation regression suite catching a deliberately introduced regression (e.g., a prompt change that degrades a previously-passing golden-dataset task).

## Deliverables

- `packages/evaluation/pipeline.py`, `fix_rate.py`, `attribution.py`, `feedback_loop_health.py`.
- `packages/evaluation/benchmarks/golden_dataset.py`, `shadow_mode.py`.
- DORA metrics dashboard (Grafana, per `techstack.md`).

## Sections

1. [Automated Scoring Pipeline & KPI Store](section-01.md)
2. [Golden Dataset & Shadow-Mode Graduation](section-02.md)
3. [Platform Self-Evaluation & DORA Metrics](section-03.md)
