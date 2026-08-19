# Section 02 — Golden Dataset & Shadow-Mode Graduation

## Objective

Build a golden dataset of labeled tasks with known-good outcomes, and the shadow-mode graduation harness (§L.3): agent proposes, human decides, outcomes compared — with a risk tier only becoming (semi-)autonomous once a measured resolution-rate/false-positive threshold is met empirically.

## Why It Exists

This is the empirical foundation the roadmap has been deferring since Phase 04 §04 ("v1 weights pending shadow-mode recalibration") and Phase 10 §02 ("recalibrating rule thresholds based on real outcome data") — and the mechanism that prevents the platform from ever granting itself more autonomy than evidence supports, directly enforcing Principle 5 (deterministic/auditable) with real data instead of intuition.

## Dependencies

Section 04 (`EvaluationEngine`), accumulated real task history from Phases 05–14.

## Atomic Implementation Tasks

1. Assemble the golden dataset: a curated set of tasks with known-correct outcomes, reusing the query-taxonomy discipline established in Phase 03 §06's retrieval benchmark and Phase 11 §05's scale benchmark.
2. Implement shadow-mode harness: run the platform's proposed decision (e.g., an auto-merge-eligibility call) alongside a required human decision, without acting on the platform's proposal, and log agreement/disagreement.
3. Implement the graduation threshold check: a risk tier becomes eligible for reduced oversight only after a defined resolution-rate/false-positive threshold is met over a minimum sample size — document the chosen thresholds explicitly as a decision, not a given.
4. Recalibrate the Confidence Model weights (§B.4, deferred since Phase 04 §04) via logistic regression against golden dataset outcomes, including the drop-one ablation for `retrieval_coverage`/`validator_agreement` correlation the blueprint specifically calls for.

## Manual Testing Procedure

Run the golden dataset through shadow mode and review the agreement-rate report; manually inspect a handful of disagreements to sanity-check them.

## Expected Demo

Golden-dataset resolution rate printed as a tracked metric, plus the recalibrated confidence weights compared against the original v1 starter values.

## Acceptance Criteria

- [ ] Golden-dataset resolution rate is a tracked, trending metric with a documented baseline — the blueprint's explicit Phase 15 completion criterion.
- [ ] Confidence Model weights are recalibrated against real outcome data, with the ablation study documented.
- [ ] No risk tier's oversight is reduced without passing its graduation threshold — enforced in code, not just policy.

## Risks

A golden dataset too small or unrepresentative could yield misleading graduation decisions — treat this as an ongoing, growing artifact, not a one-time build.

## Future Improvements

Expand golden dataset coverage as more task categories accumulate real history.
