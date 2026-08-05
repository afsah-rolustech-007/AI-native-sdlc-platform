# Section 05 — Token Efficiency Benchmark

## Objective

Produce the direct, quantitative proof of this phase's stated goal: run equivalent representative tasks with context engineering disabled (Phase 11 baseline behavior) versus fully enabled (Sections 01–04), measuring total tokens per task and task success rate, targeting ≥40% token reduction with no drop in success rate.

## Why It Exists

Every other section in this phase built a mechanism plausibly aimed at efficiency; this section is where "plausibly" becomes "measured." Consistent with `development_strategy.md`'s core lifecycle (never defer testing to the end), this benchmark should ideally be run incrementally as each of Sections 01–04 lands, not saved entirely for the end — but this final version is the phase's official, complete before/after comparison.

## Expected Architecture

`tests/benchmark/context_efficiency.py` selects a representative set of tasks (reusing demo scenarios and any accumulated real task history from Phases 05–11) and runs each twice: once with a feature flag disabling Sections 01–04 (falling back to Phase 11's unbudgeted, uncompressed, raw-artifact-passing behavior), once with them fully enabled. For each run, records total tokens (input+output, from `cost_tracking`, Phase 00/02) and the task's final QA/Spec-QA outcome (pass/fail, from Phase 07). Aggregates the token delta and confirms no success-rate regression.

## Dependencies

Sections 01–04 (the full context-engineering system to benchmark), Phase 00/02 (cost tracking), Phase 07 (QA outcome as the success-rate proxy).

## Atomic Implementation Tasks

1. Implement the feature-flag toggle allowing context engineering to be fully disabled for comparison purposes (this is useful beyond this one benchmark — a reasonable debugging tool to keep around).
2. Select a representative task set spanning the different phases' demo scenarios (requirements-heavy, design-heavy, implementation-heavy, QA-heavy) so the benchmark isn't skewed toward one phase's efficiency gains.
3. Run each task in the set twice (flag off, flag on), recording total tokens and QA outcome for each run.
4. Compute the aggregate token reduction percentage and confirm the success-rate (QA pass rate) is not regressed.
5. If the 40% target isn't met, use Section 01's per-agent budget-vs-actual metrics to identify which agents/phases are contributing least to the reduction, and revisit the relevant section (02, 03, or 04) before re-benchmarking.
6. Document the final results in `docs/decisions/`, alongside Phase 11's retrieval-precision benchmark, as a growing permanent record of the platform's own measured efficiency/quality tradeoffs over time.

## Manual Testing Procedure

1. Run the full benchmark suite and review the per-task and aggregate token reduction numbers.
2. Manually spot-check 2–3 tasks' QA outcomes in both configurations to confirm the "no success-rate regression" claim isn't hiding a subtle quality difference the pass/fail signal alone might miss (e.g., re-read the actual generated code/design for both runs of at least one task).
3. If any task's outcome differs between flag-off and flag-on runs, investigate specifically — this is the most important signal the benchmark can produce.

## Expected Demo

This section's demo *is* Phase 12's overall live demo (see README): the final aggregate token-reduction percentage printed against the 40% target, alongside a side-by-side QA-outcome comparison table proving no success-rate regression.

## Acceptance Criteria

- [ ] Average tokens per task drop ≥40% versus the Phase 11 baseline — the blueprint's explicit Phase 12 completion criterion, measured directly.
- [ ] No drop in task success rate (QA pass rate) between the two configurations.
- [ ] Any task exhibiting an outcome difference between configurations is individually investigated and explained, not averaged away.

## Risks

- **Risk:** A benchmark task set too small or too narrowly scoped could produce a misleadingly favorable (or unfavorable) result. **Mitigation:** deliberately span multiple phases' demo scenarios (task 2) rather than optimizing the benchmark set toward whichever tasks happen to compress best.

## Future Improvements

- Continuous token-efficiency tracking as part of Phase 15's broader evaluation framework, rather than a one-time before/after comparison.

## Research Opportunities

This benchmark, once established, is a natural candidate to become one of Phase 15's platform self-evaluation regression checks (§L.4) — re-run whenever context-engineering logic changes, to catch efficiency regressions the same way Phase 01 §04's chaos harness catches durability regressions.
