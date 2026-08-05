# Section 05 — Scale Benchmarking Against the Phase 3 Baseline

## Objective

Re-run the exact retrieval-precision benchmark methodology from Phase 03 §06 against the larger, federated corpus, producing the blueprint's explicit Phase 11 completion criterion: retrieval precision@5 within 5 points of the Phase 03 baseline at scale.

## Why It Exists

Federation (Sections 01–04) is only a success if it preserves retrieval quality while enabling scale — this section is the direct, quantitative proof, closing the loop on the baseline Phase 03 §06 deliberately established for exactly this future comparison.

## Expected Architecture

`tests/benchmark/retrieval_precision_at_scale.py` reuses Phase 03 §06's benchmark methodology (same query-type taxonomy: symbol lookup, caller lookup, similar-implementation, concept search) but hand-labels a new set of queries against the larger corpus (the original fixture-repo labels don't transfer to a different corpus). Runs the same precision@5 computation, and additionally breaks results down by whether each query was shard-local or cross-shard, to isolate whether any precision loss concentrates in one category.

## Dependencies

Sections 01–04 (the full federated system to benchmark), Phase 03 §06 (the baseline methodology and number to compare against).

## Atomic Implementation Tasks

1. Hand-label a new benchmark query set against the larger corpus, following the same methodology and query-type taxonomy as Phase 03 §06 (same rigor: label before observing system behavior, include adversarial/ambiguous queries).
2. Run the benchmark against the federated system, computing overall and per-query-type precision@5.
3. Break down results by shard-local vs. cross-shard query performance specifically — this is the diagnostic that tells you *where* to look if the aggregate number misses the 5-point target.
4. If the target is missed, investigate using the breakdown (e.g., is cross-shard concept routing, Section 02 task 3, the culprit?) and iterate on the relevant section before re-benchmarking — this is exactly the "build v1, measure, revise" loop `roadmap.md` §3 flags as expected for this phase's research-heavy classification.
5. Document the final result and methodology in `docs/decisions/`, alongside the Phase 03 baseline, as a permanent before/after record.

## Manual Testing Procedure

1. Run the full benchmark and review the per-query-type and per-locality breakdown, not just the aggregate score.
2. Spot-check any underperforming query category by hand to understand root cause before attributing it to "scale" generically.

## Expected Demo

This section's demo *is* Phase 11's overall live demo (see README): the final precision@5 score printed alongside the Phase 03 baseline, explicitly showing the delta and confirming it's within the 5-point target — or, if not yet met, a documented explanation of the gap and the remediation plan.

## Acceptance Criteria

- [ ] Retrieval precision@5 at scale is within 5 points of the Phase 03 baseline — the blueprint's explicit Phase 11 completion criterion, measured and documented.
- [ ] Results are broken down by shard-local vs. cross-shard query performance.
- [ ] Any precision gap found is investigated to a specific root cause, not left as an unexplained aggregate number.

## Risks

- **Risk:** A benchmark built by the same engineer who built the federation system risks the same unconscious-bias concern flagged in Phase 03 §06. **Mitigation:** apply the same discipline — label before observing, include adversarial cases — and additionally consider having queries include some that specifically probe suspected weak points (e.g., a concept clearly split across two shards) rather than only "easy" queries.

## Future Improvements

- Continuous benchmark tracking (not just a one-time before/after) as the corpus and federation evolve — a natural precursor to Phase 15's broader evaluation framework.

## Research Opportunities

This benchmark's methodology is a strong candidate to become a recurring regression check once Phase 15's platform self-evaluation (§L.4) exists — retrieval precision is exactly the kind of metric that should be re-checked whenever the sharding/indexing logic changes, not just once at the end of Phase 11.
