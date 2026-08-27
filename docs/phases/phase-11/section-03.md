# Section 03 — NetworkX → Neo4j Migration

## Objective

Migrate the dependency/call graph backend from Phase 03's in-process NetworkX to Neo4j, per the blueprint's explicit MVP→scale path (§G.3), enabling multi-hop Cypher queries across a graph too large to comfortably hold in a single process's memory, and supporting genuinely concurrent readers (multiple tasks querying simultaneously).

## Why It Exists

This is the payoff for `architecture.md` §4.1's design decision to hide the graph backend behind `RepositoryIntelligence` from day one: this migration should be a backend swap, not a rewrite, because no agent code (Phases 04–10) ever imported NetworkX directly.

## Expected Architecture

`packages/repo_intel/graph/neo4j_client.py` implements the same internal interface Phase 03's `networkx_client.py` exposed (`get_callers`, `get_callees`, `get_dependencies`, `get_dependents`, `get_impact_set` — all backed by Cypher queries instead of in-memory graph traversal), scoped per-shard (Sections 01–02) with cross-shard edges stored in a way queryable from the global index-of-indices. A migration script transforms Phase 03's NetworkX graph construction pipeline's *output* (the extracted edges) into Neo4j `CREATE`/`MERGE` statements, run once per shard during initial federation setup, then maintained incrementally via the same **working-tree content-hash** pattern from Phase 03 §05 (not git-diff).

## Dependencies

Section 01 (shards to scope Neo4j instances/databases to), Phase 03 §03 (the NetworkX implementation and its edge-extraction logic being migrated).

## Atomic Implementation Tasks

1. Stand up Neo4j (single instance with per-shard databases, or per-shard instances — decide based on the corpus size and document the choice; Neo4j Community Edition's multi-database support is likely sufficient at this phase's scale).
2. Implement the edge-extraction-to-Cypher migration script, reusing Phase 03 §03's edge extraction logic unchanged (only the storage/query backend changes).
3. Re-implement `get_callers`/`get_callees`/`get_dependencies`/`get_dependents`/`get_impact_set` as Cypher queries against Neo4j, preserving exact input/output contracts from Phase 03's NetworkX implementation.
4. Update the incremental indexing pipeline (Phase 03 §05) to write incremental graph updates to Neo4j instead of rebuilding an in-memory NetworkX graph.
5. Run Phase 03 §03's exact unit tests (known caller/callee relationships, impact-set correctness) against the new Neo4j-backed implementation and confirm identical results.
6. Benchmark query latency for multi-hop queries (e.g., `get_callers` at depth 3+) at the larger corpus scale, comparing against what a NetworkX-based approach would require (either by testing NetworkX at this scale directly if feasible, or reasoning from memory/complexity characteristics if not).

## Manual Testing Procedure

1. Run Phase 03's exact test scenarios against the migrated Neo4j backend and confirm identical results.
2. Run a multi-hop query at the larger corpus scale and confirm latency is acceptable (define "acceptable" relative to the interactive agent-tool-call context these queries serve — sub-second is a reasonable target, document the actual measured figure).
3. Confirm concurrent read queries (simulate 2+ simultaneous callers) work correctly without contention issues that an in-process NetworkX graph would have had under concurrent access.

## Expected Demo

Terminal output comparing the same multi-hop query's result and latency between the original Phase 03 NetworkX implementation (on the smaller fixture repo) and the new Neo4j implementation (on the larger corpus) — the point isn't a like-for-like speed comparison (different scales), but proving correctness is preserved and scale-appropriate latency is achieved.

## Acceptance Criteria

- [ ] All Phase 03 §03 dependency-graph tests pass identically against the Neo4j-backed implementation.
- [ ] No agent code from Phases 04–10 required any modification for this migration — verified by running their existing test suites unmodified.
- [ ] Multi-hop query latency at the larger corpus scale is measured and documented as acceptable for interactive agent use.
- [ ] Concurrent read access works correctly, addressing the exact limitation (embedded, single-process) that motivated rejecting KuzuDB in the blueprint's own comparative analysis (§0.2 #4).

## Risks

- **Risk:** Cypher query performance can degrade badly with poorly-designed graph schema (e.g., missing indexes on frequently-queried node properties). **Mitigation:** add appropriate Neo4j indexes on symbol/file identifiers as a first-class task, not an afterthought — this is a common, well-documented Neo4j pitfall worth proactively avoiding.

## Future Improvements

- Neo4j clustering for HA/horizontal read scaling — a Phase 16-adjacent production-hardening concern if real load testing (Phase 16) reveals it's needed.

## Research Opportunities

None — this is a well-trodden migration path (NetworkX prototypes to Neo4j production graphs are common); the interesting research in this phase is Section 01's shard-boundary work, not this migration.
