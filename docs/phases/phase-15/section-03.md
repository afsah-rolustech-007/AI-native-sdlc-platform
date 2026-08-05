# Section 03 — Platform Self-Evaluation & DORA Metrics

## Objective

Implement the platform self-evaluation regression suite (§L.4: re-run the golden dataset against every platform change — prompt, model, graph — before it ships) and DORA metrics (§L.5: Deployment Frequency, Lead Time, Change Failure Rate, MTTR) as an operational dashboard.

## Why It Exists

§L.4 is the platform's own CI for itself — treating prompts and graph topology as the versioned artifacts they are, with the same regression discipline the platform enforces on the code it generates. DORA metrics give a standard, externally-legible measure of whether the platform is actually delivering faster/safer software, tying back to the project's core motivation.

## Dependencies

Section 02 (golden dataset to regress against), Phase 08 §05 (`DeploymentRecord` data for DORA metrics).

## Atomic Implementation Tasks

1. Implement the platform self-evaluation CI job: re-run the golden dataset against a proposed prompt/model/graph change, diff results against the current baseline, block the change on regression.
2. Test this by deliberately introducing a prompt regression (e.g., a change that removes a key instruction) and confirming the CI job catches the resulting golden-dataset score drop.
3. Implement DORA metrics computation from `DeploymentRecord` (Phase 08 §05) and `rollback_count`/incident data (Phase 08 §05's `MonitoringManager`).
4. Build a Grafana dashboard (per `techstack.md`) surfacing DORA metrics and the KPI trends from Section 01.

## Manual Testing Procedure

Introduce a deliberate prompt regression on a branch, run the self-evaluation CI job, and confirm it flags the regression before merge; separately, verify DORA metrics compute correctly against known `DeploymentRecord` history.

## Expected Demo

The self-evaluation CI job catching the deliberately introduced regression, plus the Grafana dashboard showing live DORA metrics and KPI trends — this is the phase's headline demo per the README.

## Acceptance Criteria

- [ ] The self-evaluation CI job successfully blocks a deliberately regressive platform change.
- [ ] DORA metrics compute correctly and are visible on a live dashboard.

## Risks

Self-evaluation is only as good as golden dataset coverage (Section 02's risk) — a regression outside covered categories won't be caught; this is a known, documented limitation, not a silent gap.

## Future Improvements

None planned beyond expanding golden dataset coverage (Section 02).
