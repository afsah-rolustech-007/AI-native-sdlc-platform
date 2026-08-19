# Section 05 — Experiments, Baseline Diff & Self-Evaluation CI

## Objective

Implement §L.8: `evaluation_experiments` rows, a baseline experiment, replay of the golden dataset (Section 02) under a changed prompt/model/sha, per-`metric_id` diff, CI gate on MVP metrics only.

## Why It Exists

§L.4's "re-run golden set when prompts change" is an experiment, not a dashboard. This section is the answer to "did this change improve the system, and which version field moved?"

## Expected Architecture

`packages/evaluation/experiments.py`:

- `create_experiment(...)` writes §R `evaluation_experiments`.
- `run_dataset(experiment_id, dataset)` invokes the **same** task runner used in production (worker entrypoint), with `experiment_id` set on `TelemetrySink` task attributes.
- `diff_baseline(experiment_id) -> list[{case_id, metric_id, delta}]`.
- CI job: fail if any MVP metric (documented list in `configs/evaluation/mvp_gate.yaml`) drops by more than epsilon.

Change **one** of `{prompt_version, model_ids, agent_version}` per experiment for attribution.

Do not add MLflow. Do not call Langfuse as an eval API.

## Dependencies

Section 02 (dataset), Section 04 (`EvaluationEngine`), Section 01 (persist scores).

## Atomic Implementation Tasks

1. Alembic for `evaluation_experiments` / `evaluation_scores` if not created in Phase 00 (Phase 00 may scaffold empty tables per §R — if so, only backfill columns here).
2. Implement create / run / diff.
3. CI workflow: on prompt or `packages/agents` change, run a **small** golden subset (not full set on every commit — full set on main or nightly). Document the subset in the YAML.
4. Deliberate prompt regression test: CI fails.
5. Unit test `diff_baseline` with two fake `EvaluationResult` sets.

## Manual Testing Procedure

Introduce a prompt regression on a branch; run the CI job; confirm block.

## Expected Demo

CI log showing metric deltas vs baseline and a red gate.

## Acceptance Criteria

- [ ] Baseline + candidate experiments stored in Postgres.
- [ ] Gate uses only MVP deterministic metrics (§L.7).
- [ ] LLM-judge scores cannot fail CI.

## Risks

Golden subset too small — documented limitation; expand coverage rather than weakening the gate.

## Future Improvements

Nightly full-dataset run. Judge-agreement jobs (Advanced, §L.9) — never on the merge gate until calibrated.
