# Phase 03 — Minimal Repository Intelligence

## Goal

Working code retrieval — symbol parsing, lexical search, semantic search, and incremental updates — at small scale (a few hundred to low-thousands of files), proven against a real held-out labeled retrieval benchmark, before any scaling work (Phase 11) or any agent (Phase 05+) depends on it.

## Why This Phase Exists

The Dynamic Requirements Engine (Phase 04) and every design/implementation/QA agent from Phase 05 onward is only as good as what it can retrieve about the actual codebase. Building retrieval correctness first, at a scale small enough to hand-label a benchmark, means later phases inherit a *proven* retrieval layer instead of an assumed one. Corresponds to `final_plan.md` §G at MVP scope (Layers L0–L3; L4 architecture summary), using the tool stack decided in §G.3/§0.1 (Tree-sitter, Zoekt, NetworkX, pgvector — not SCIP, not KuzuDB).

## Dependencies

Phase 00 (Postgres/pgvector, sandbox for running indexer subprocesses safely), Phase 02 (embedding calls go through `ModelAdapter.embed()`).

## High-Level Architecture

```
Git repo (working directory) ──▶ git hooks / diff watcher (incremental trigger)
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
             Tree-sitter parser    Zoekt indexer          Embedding pipeline
             (L1: AST/symbols)     (L0/L1: trigram search)  (L3: pgvector)
                    │                     │                     │
                    └──────────┬──────────┴──────────┬──────────┘
                               ▼                     ▼
                    NetworkX dependency graph   RepositoryIntelligence API
                    (L2, in-process, MVP)       (single interface, §G.6 —
                               │                 structural + semantic subset
                               └────────────────▶ only; hybrid RRF fusion and
                                                  historical methods are
                                                  Phase 11/12 extensions)
```

## Expected Live Demo

Point the indexer at a real small-to-medium open-source repo (or this platform's own future codebase, once it exists). Run a batch of ~20 hand-labeled queries ("where is X defined," "what calls Y," "find code similar to Z") through `RepositoryIntelligence`, compute precision@5, and print the score against the ≥90% target. Then make a small edit to the repo, show incremental re-indexing completes in under 10 seconds, and re-run one query to prove the index reflects the change.

## Deliverables

- `packages/repo_intel/indexers/treesitter.py` — symbol index.
- `packages/repo_intel/indexers/zoekt_client.py` — trigram search integration.
- `packages/repo_intel/indexers/incremental.py` — git-diff-triggered re-indexing.
- `packages/repo_intel/vector/pgvector_client.py` — embedding store.
- `packages/repo_intel/graph/networkx_client.py` — MVP dependency graph.
- `packages/repo_intel/api.py` — `RepositoryIntelligence` structural + semantic methods (subset of §G.6).
- `tests/benchmark/retrieval_precision.py` — held-out labeled query benchmark.

## Sections

1. [Tree-sitter Symbol Index (L1)](section-01.md)
2. [Zoekt Trigram Search Integration (L0/L1)](section-02.md)
3. [NetworkX Dependency Graph (L2, MVP)](section-03.md)
4. [pgvector Semantic Embeddings (L3)](section-04.md)
5. [Git-Diff Incremental Indexing](section-05.md)
6. [RepositoryIntelligence API & Retrieval Precision Benchmark](section-06.md)
