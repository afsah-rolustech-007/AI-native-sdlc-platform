# Section 04 — Nightly Full Re-Index at Scale

## Objective

Extend Phase 03 §05's nightly full re-index "drift-safety net" to operate correctly across a federated, sharded corpus — parallelized across shards so that a full re-index of a 100k–1M+ file corpus remains operationally feasible on a nightly cadence.

## Why It Exists

At small scale (Phase 03), a full re-index is cheap enough that its cost is almost incidental. At the scale this phase targets, a naive sequential full re-index could take longer than the time available before the next business day — this section is where that assumption gets explicitly tested and, if needed, addressed via shard-parallel execution.

## Expected Architecture

`packages/repo_intel/indexers/coordinator.py` (the "sharded parallel indexer" named in §Q's project structure) orchestrates one re-index job per shard, dispatched concurrently (via Phase 00's ARQ worker pool, scaled appropriately), each shard's re-index independent and isolated (a failure in one shard's re-index does not block others). After all shards complete, the global index-of-indices (Section 02) is rebuilt from the updated shard-level summaries.

## Dependencies

Section 01 (shards), Section 02 (global index rebuild), Phase 00 §06 (ARQ worker infrastructure).

## Atomic Implementation Tasks

1. Implement `coordinator.py`'s shard-dispatch logic: one re-index job per shard, submitted to the worker pool concurrently.
2. Implement per-shard failure isolation: a failed shard re-index is logged and retried/alerted, without blocking or failing other shards' re-indexes.
3. Implement the global index-of-indices rebuild step, triggered after all (or a configurable quorum of) shard re-indexes complete.
4. Implement timing instrumentation: total wall-clock time for a full re-index at the larger corpus scale, and per-shard breakdown.
5. Load test: run the full nightly re-index against the larger corpus and measure total time; if it exceeds a reasonable nightly-window budget (define this explicitly, e.g., "must complete within 4 hours"), investigate whether additional worker parallelism or shard-level optimization is needed.

## Manual Testing Procedure

1. Trigger a full re-index manually against the larger corpus and time it end to end.
2. Deliberately fail one shard's re-index (e.g., inject a fault) and confirm other shards' re-indexes complete unaffected.
3. Confirm the global index-of-indices correctly reflects all successfully-updated shards after the run.

## Expected Demo

A timed, terminal-logged full re-index run across all shards, showing per-shard completion times and the total wall-clock time against the documented target budget — plus a demonstration of one shard's isolated failure not affecting the others.

## Acceptance Criteria

- [ ] Full re-index is parallelized across shards, not sequential.
- [ ] A single shard's re-index failure does not block or fail other shards.
- [ ] Total re-index time at the larger corpus scale is measured and meets a documented, reasonable nightly-window target.
- [ ] The global index-of-indices is correctly rebuilt after a full re-index.

## Risks

- **Risk:** Worker pool resource contention if all shards' re-indexes are dispatched simultaneously without any concurrency cap. **Mitigation:** make shard-dispatch concurrency configurable and tune it against actual available worker capacity, rather than assuming unlimited parallelism is free.

## Future Improvements

- Incremental-only nightly runs (skip shards with no changes since last incremental update) — a reasonable optimization once real usage patterns show most shards are quiet most nights.

## Research Opportunities

None — this is an operational scaling exercise, not an open design question.
