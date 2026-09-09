# Phase 03 — Minimal Repository Intelligence

## Goal

Working code retrieval — symbol parsing, lexical search, semantic search, and incremental updates — at small scale (a few hundred to low-thousands of files), proven against a real held-out labeled retrieval benchmark, before any scaling work (Phase 11) or any agent (Phase 05+) depends on it.

**Source of truth for this phase: the local working tree** (the files currently on disk under a configured `repo_root`), including uncommitted edits. Git commits, remotes, branches, pull/push, and git hooks are **not** Phase 03 requirements.

## Why This Phase Exists

The Dynamic Requirements Engine (Phase 04) and every design/implementation/QA agent from Phase 05 onward is only as good as what it can retrieve about the actual codebase. Building retrieval correctness first, at a scale small enough to hand-label a benchmark, means later phases inherit a *proven* retrieval layer instead of an assumed one. Corresponds to `final_plan.md` §G at MVP scope (Layers L0–L3; L4 architecture summary), using the tool stack decided in §G.3/§0.1 (Tree-sitter, Zoekt, NetworkX, pgvector — not SCIP, not KuzuDB).

This MVP is a **single-engineer local repo**. Indexing must reflect what the engineer (and later, agents) just wrote on disk, not what was last committed.

## Dependencies

Phase 00 (Postgres/pgvector, sandbox for running indexer subprocesses safely), Phase 02 (embedding calls go through `ModelAdapter.embed()`).

## High-Level Architecture

```
Local working tree (repo_root on disk, including uncommitted files)
        │
        │  explicit `index` / `reindex`  (content-hash catalog)
        │  optional `reindex_paths([...])` after an agent writes files
        ▼
 indexed_files catalog  (path, sha256, size, mtime hint)
        │
        ├── changed / created / deleted paths only
        │
        ├─▶ Tree-sitter (L1 symbols)
        ├─▶ Zoekt (L0/L1 lexical)
        ├─▶ NetworkX (L2 graph, this file's edges)
        └─▶ pgvector (L3, chunks whose content_hash changed)
                    │
                    ▼
          RepositoryIntelligence API  (§G.6 subset)
```

Git may be used later for diffs, rollback, and PRs (Phases 06/08). It is **not** how Phase 03 decides what to index.

## Indexing lifecycle (MVP)

| Trigger | When | What runs |
|---|---|---|
| `index <repo_root>` | First time, or after catalog wipe | Full walk + all four indexes |
| `reindex` | Human or script, after local edits | Hash walk → incremental update of **changed paths only** |
| `reindex_paths([files])` | After an agent writes those files (Phase 05+ contract; API exists now) | Incremental update of those paths (plus delete/create detection for them) |
| Retrieval (`get_*` / `search_*`) | On demand | **Does not** silently re-index (embedding cost). If the catalog is stale vs the working tree → `StaleIndexError` with the stale paths. Caller runs `reindex` (or `refresh=True` on the API) then retries. |

**Not in Phase 03 (DEFERRED):** filesystem watcher, git post-commit hooks, remote fetch, branch tracking, nightly full re-index job, rename-as-first-class event (treated as delete + create).

## Change detection (chosen)

On `reindex`, walk eligible files and **SHA-256 the file bytes**. Compare to the `indexed_files` catalog.

- **Why hashes, not mtimes:** mtimes lie (copy, some editors, containers, `touch`). At a few hundred to low-thousands of files, hashing is cheap and is the actual content identity.
- **Why not a watcher:** extra process, missed events, no strong MVP need. Explicit `reindex` is reliable.
- **Why not git diff:** misses uncommitted work, which *is* the product for this MVP.

`mtime` and `size` are stored as hints/debug, not as the freshness authority.

## Staleness

A file is **stale** if its working-tree SHA-256 ≠ catalog SHA-256, or it is new/deleted vs the catalog.

Staleness is **per-file**, not all-or-nothing. Retrieval is **blocked** (`StaleIndexError`) if any eligible path is stale — fail-closed: never answer as if the index were current. The error lists stale paths so the caller can `reindex` (or `reindex_paths`) without guessing.

## Expected Live Demo

Point the indexer at a small fixture tree (or this repo). Run a batch of ~20 hand-labeled queries through `RepositoryIntelligence`, compute precision@5 against the ≥90% target. Then **edit a file on disk without committing**, run `reindex`, show it finishes in under 10 seconds for a 1–20 file change, and re-run a query proving the index reflects the uncommitted edit.

> **As built:** `make benchmark` and `make ri-demo`. The metric is **success@5**, not
> precision@5 — most labeled queries have exactly one correct answer, which caps
> precision@5 at 0.20 and makes it measure label cardinality instead of retrieval quality.
> See [`tests/benchmark/README.md`](../../../sdlc-platform/tests/benchmark/README.md) for
> the rationale and the recorded baseline (96.2% overall).

## Deliverables

- `packages/repo_intel/indexers/treesitter.py` — symbol index.
- `packages/repo_intel/indexers/zoekt_client.py` — trigram search integration.
- `packages/repo_intel/indexers/catalog.py` — working-tree walk, ignore rules, SHA-256 catalog.
- `packages/repo_intel/indexers/incremental.py` — content-hash incremental re-index (not git).
- `packages/repo_intel/vector/pgvector_client.py` — embedding store.
- `packages/repo_intel/graph/networkx_client.py` — MVP dependency graph.
- `packages/repo_intel/api.py` — `RepositoryIntelligence` structural + semantic methods (subset of §G.6).
- `tests/benchmark/retrieval_precision.py` — held-out labeled query benchmark.

## Sections

1. [Tree-sitter Symbol Index (L1)](section-01.md)
2. [Zoekt Trigram Search Integration (L0/L1)](section-02.md)
3. [NetworkX Dependency Graph (L2, MVP)](section-03.md)
4. [pgvector Semantic Embeddings (L3)](section-04.md)
5. [Working-Tree Incremental Indexing](section-05.md)
6. [RepositoryIntelligence API & Retrieval Precision Benchmark](section-06.md)
