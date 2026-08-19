# Section 03 — Platform Self-Evaluation & DORA Metrics

## Objective

Implement DORA metrics (§L.5) from `DeploymentRecord` and incident/rollback data, and a Grafana dashboard for DORA plus KPI trends from `evaluation_results`.

## Why It Exists

DORA is the externally-legible delivery view. Platform regression **gating** lives in Section 05 (experiments), not here — this section is visualization.

## Dependencies

Section 01 (KPI rows), Phase 08 §05 (`DeploymentRecord`).

## Atomic Implementation Tasks

1. Compute DORA four keys from `DeploymentRecord` + rollback/incident data.
2. Grafana dashboard: DORA + `fix_rate` / `cost_usd` / `cycle_time_s` trends.
3. Test DORA formulas against known `DeploymentRecord` history.

## Manual Testing Procedure

Verify DORA numbers against a hand-calculated week of demo deploys.

## Expected Demo

Grafana showing DORA + KPI trends.

## Acceptance Criteria

- [ ] DORA metrics compute correctly and are visible on a live dashboard.

## Risks

Low deploy volume in solo-dev makes DORA noisy — show raw counts alongside rates.

## Future Improvements

None beyond dataset coverage.
