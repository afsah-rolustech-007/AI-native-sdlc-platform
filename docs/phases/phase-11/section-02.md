# Section 02 — Global Index-of-Indices & Cross-Shard Query Routing

## Objective

Implement the global index-of-indices (§G.4): a lightweight, always-hot index storing only shard boundaries, cross-shard dependency edges, and shard-level L4 summaries — plus the query-routing logic that resolves any incoming query to the relevant shard(s) before drilling into full per-shard indices.

## Why It Exists

This is the mechanism that keeps query cost proportional to task relevance rather than total repo size (§G.4's stated problem statement) — without it, every query would need to consult every shard, defeating the purpose of sharding at all.

## Expected Architecture

`packages/repo_intel/sharding/global_index.py` maintains a small, always-in-memory-or-fast-cache structure: `{shard_id: {boundary_paths, summary}}` plus a `cross_shard_edges: [{from_shard, to_shard, via_symbol}]` list. `RepositoryIntelligence`'s existing public methods (§G.6, unchanged interface) are extended internally: a query first resolves candidate shard(s) via the global index (e.g., by file path prefix matching, or by a lightweight semantic match against shard-level L4 summaries for concept-based queries), then delegates to Section 01's identified shard(s)' full indices for the actual answer. Cross-shard queries (e.g., "what calls this API org-wide") explicitly route through the cross-shard edge index first, then fan out to the relevant target shards.

## Dependencies

Section 01 (shard boundaries), Phase 03 §06 (`RepositoryIntelligence` interface to preserve).

## Atomic Implementation Tasks

1. Implement the global index-of-indices data structure and its build process (derived from Section 01's finalized shard boundaries plus each shard's L4 architecture summary, Phase 03 §06).
2. Implement shard resolution for path-scoped queries (`get_symbol_signature`, `get_file_structure`, etc.) — trivial path-prefix matching against shard boundaries.
3. Implement shard resolution for concept-scoped queries (`search_concepts`) — a coarse-grained semantic match against shard-level summaries before drilling into the resolved shard's full vector index (avoiding a full cross-shard vector search for every query).
4. Implement cross-shard query routing (`get_callers`/`get_impact_set` when the target's callers may span shards) using the cross-shard edge index specifically, per §G.4's stated query flow.
5. Update `RepositoryIntelligence`'s internal implementation to use this routing layer, with **zero changes to its public method signatures** — verified by re-running every existing Phase 03–10 agent's tests unmodified against the now-sharded backend.
6. Integration test: a query scoped to one shard resolves and answers correctly without touching other shards (verified via instrumentation/counting which shards were actually queried); a genuine cross-shard query (e.g., a symbol in shard A called from shard B) correctly resolves via the cross-shard edge index.

## Manual Testing Procedure

1. Run a shard-local query and confirm (via added instrumentation) only the relevant shard was queried.
2. Run a genuine cross-shard query and confirm the cross-shard edge index was consulted and the correct cross-shard result returned.
3. Re-run Phase 03's retrieval-precision benchmark queries (adapted to the larger corpus) through the sharded implementation and confirm no interface-level regression for any agent code from Phases 04–10.

## Expected Demo

Terminal output showing query-routing instrumentation for both a shard-local and a cross-shard query, proving the "drill into only relevant shards" property holds — plus confirmation that a Phase 06 CodeGen agent's existing tool-calling code runs unmodified against this new backend.

## Acceptance Criteria

- [ ] Shard-local queries touch only their resolved shard(s), verified via instrumentation.
- [ ] Cross-shard queries correctly use the cross-shard edge index and return correct results spanning shards.
- [ ] `RepositoryIntelligence`'s public interface is byte-for-byte unchanged — every Phase 04–10 caller works without modification against the sharded backend.

## Risks

- **Risk:** Concept-scoped query routing (task 3) via coarse shard-summary matching could misroute a query to the wrong shard, missing the correct answer entirely (a precision regression, not just a performance one). **Mitigation:** Section 05's scale benchmark against the Phase 03 baseline is the direct, quantitative check for this — treat any precision drop beyond the stated 5-point tolerance as a signal to widen the concept-routing fallback (e.g., querying a small number of top-candidate shards rather than just one) rather than accepting the regression.

## Future Improvements

- Query result caching at the global-index layer for frequently-resolved shard lookups — a reasonable performance optimization once real query patterns are observed at scale.

## Research Opportunities

Compare coarse concept-routing accuracy (task 3) against always fanning out to all shards for concept queries specifically (accepting the cost) — an empirical tradeoff worth measuring directly with Section 05's benchmark data once available.
