# Phase 11 — Repository Intelligence at Scale

## Goal

Extend Phase 03's proven Repository Intelligence from a few-hundred-file fixture repo to 100k–1M+ file enterprise scale: federated domain shards, a global index-of-indices, a NetworkX→Neo4j graph migration, and nightly full re-indexing at scale — while keeping the `RepositoryIntelligence` interface (§G.6) completely unchanged from what every agent (Phases 04–10) already depends on.

## Why This Phase Exists

Per `roadmap.md` §2.2, this phase only needs Phase 03 "proven" — it does not need Phases 04–10 to exist. It's placed here (after the critical path) rather than immediately after Phase 03 deliberately: per `roadmap.md` §2.3, the core safety loop (00–10) is worth proving completely before investing in scale, so a design flaw discovered in the core loop doesn't invalidate scaling work done prematurely. This is also explicitly one of the roadmap's "research-heavy" phases (`roadmap.md` §3) — shard boundary validation against real dependency graphs is an empirical question, not a formula.

## Dependencies

Phase 03 (proven retrieval precision baseline; the `RepositoryIntelligence` interface this phase must preserve).

## High-Level Architecture

```
                    Global Index-of-Indices
              (shard boundaries, cross-shard edges,
               shard-level L4 summaries only)
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   Shard A (e.g.,      Shard B (e.g.,      Shard C (e.g.,
   "auth" service)     "payments" service) "notifications")
   ├── own AST index    ├── own AST index   ├── own AST index
   ├── own vector idx   ├── own vector idx  ├── own vector idx
   └── own dep graph    └── own dep graph   └── own dep graph
   (Neo4j, migrated     (Neo4j)             (Neo4j)
    from Phase 3's
    NetworkX)

Query flow:
  1. Query hits global index-of-indices → resolves relevant shard(s)
  2. Drills into only those shards' full indices
  3. Cross-shard query ("who calls this org-wide") → cross-shard edge index

Same RepositoryIntelligence interface (§G.6) as Phase 3 — no agent code changes.
```



## Expected Live Demo

Using a larger corpus (a real large open-source monorepo, or a synthetically assembled large corpus if a suitable real one isn't available) partitioned into at least 3 domain shards validated against real dependency-graph boundaries (not directory structure alone), demonstrate: a query resolving to exactly the right shard(s); a cross-shard query correctly using the cross-shard edge index; retrieval precision@5 measured against the Phase 03 methodology, within 5 points of the Phase 03 baseline; and a timed nightly full re-index run at this larger scale.

## Deliverables

- `packages/repo_intel/graph/neo4j_client.py` — Neo4j-backed graph, migrated from Phase 03's NetworkX.
- Shard partitioning + boundary validation tooling.
- Global index-of-indices.
- Federated query routing inside `RepositoryIntelligence` (interface unchanged, implementation extended).
- Scale benchmark comparing against the Phase 03 baseline.



## Sections

1. [Domain Shard Partitioning & Boundary Validation](section-01.md)
2. [Global Index-of-Indices & Cross-Shard Query Routing](section-02.md)
3. [NetworkX → Neo4j Migration](section-03.md)
4. [Nightly Full Re-Index at Scale](section-04.md)
5. [Scale Benchmarking Against the Phase 3 Baseline](section-05.md)

