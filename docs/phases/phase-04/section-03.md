# Section 03 — Session Repository Snapshot

## Objective

Build a **session-level, compact, cached** repository situation model for the requirements engine. Generate it once per session from Phase 03 metadata (plus a bounded manifest read). Do **not** create a second architecture summary, and do **not** scan or embed the tree.

## Why It Exists

Literal section-03 called RI **per auto-answerable question**. Every `RepositoryIntelligence` read already walks the working tree and SHA-256s eligible files (`assert_fresh`). Repeating `get_architecture_summary()` is worse: it also loads **all symbols** (`api.py` `_all_symbols`) and builds unbounded JSON (`cross_service_dependencies` is every cross-service edge).

A session snapshot answers cheap questions ("how many services?", "is there an `auth/` tree?", "what languages?") without dumping the repository into the LLM.

## Expected Architecture

`snapshot.py` + `manifests.py`. The snapshot is a Phase 04 object. **Do not add it to the RI API** (no Phase 03 contract change).

### Generated once

On session start, after `index_status()`:

1. If `unindexed` or `stale` → fail closed (`StaleIndexError` / explicit engine error). The CLI may tell the operator to `reindex`. The engine must **not** pass `refresh=True` (that embeds).
2. `get_architecture_summary()` **one call**.
3. `get_aider_repo_map(top_n=20)` **one call**.
4. Bounded manifest extract (below).
5. Record RI capability: if a cheap probe is needed, treat missing Zoekt/embeddings as **capability flags**, not as "no matches."

Cache key: `(repo_root, catalog_hash)`. Reuse for the whole session. Rebuild only when `catalog_hash` changes or a later RI call raises `StaleIndexError` (then stop auto-answer; do not keep using the old snapshot as if current).

### What is in the snapshot

| Field | Source | LLM? |
|---|---|---|
| `repo_root`, `catalog_hash`, `file_count`, `index_state` | `index_status` | No |
| `languages` | union of summary `tech_stack` (suffix languages) | No |
| `services` + per-service file count, entry points, key symbols, deps | capped projection of summary `service_map` | No |
| `api_boundaries`, `database_entities`, `shared_modules` | capped lists from summary | No |
| `top_files` | `get_aider_repo_map` | No |
| `manifest_facts` | allowlist disk read | No |
| `capabilities` | zoekt / embeddings / graph known-available | No |
| `truncated` + `token_estimate` | caps | No |

**Hard caps** (stay near §H.1 `ARCH_SUMMARY` ≈ 2k tokens): max 40 services (remainder as `other_service_count`); max 5 entry points and 5 key symbols per service; max 20 API / DB / shared paths; drop full `cross_service_dependencies` from the snapshot (the graph signal exists for targeted follow-up). If `file_count` is huge, prefer counts over enumerations.

### What is *not* in the snapshot

- File bodies, all symbols, all import edges
- A second LLM "repo summary"
- Framework names from `tech_stack` — Phase 03 sets `tech_stack` from **file suffix only** (`summary.py` `_LANGUAGE_BY_SUFFIX`)
- Test existence as a boolean unless a later EvidencePlan searches for it (tests have low in-degree, so they will not appear in the repo map)

### Manifest allowlist (justified extra)

Phase 03's catalog walks **only** `.py` / `.ts` / `.tsx` (`SUPPORTED_EXTENSIONS`). `pyproject.toml` / `package.json` are **not indexed**. The snapshot may read, from disk, at most these names if present, max 32 KiB each:

`pyproject.toml`, `requirements.txt`, `Pipfile`, `package.json`, `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle`

Parse enough to extract dependency **names** (not lockfile graphs). Provenance: `manifest:pyproject.toml`. This is how "is FastAPI declared?" becomes a FACT without lexical search. It is O(1) named files, not a tree walk.

### Targeted RI attaches how

The snapshot is **Tier 1 evidence**. Slots still run EvidencePlans (Section 04) when the snapshot cannot answer. Example: snapshot shows service `auth` + manifest `fastapi` → FACT "auth module exists" + FACT "FastAPI is a declared dependency." "Use JWT" stays UNKNOWN/INFERENCE until lexical/symbol evidence, and stays a DECISION if the user said it.

### Scale

| Repo size | Snapshot behavior |
|---|---|
| ~10k files (Phase 03 MVP) | One summary call is acceptable; cache it |
| ~100k | Same shape, caps bind; inherited cost is Phase 03 `_all_symbols` + whole-tree hash on every later RI read — **do not bypass `assert_fresh`** |
| 1M+ | Federation is Phase 11. Phase 04 still uses the capped projection and targeted queries; it must not enumerate services without `other_service_count` |

### Provenance

Every snapshot field used as evidence gets an `EvidenceRecord` with `retrieved_via="snapshot"` or `"manifest"` and the session `catalog_hash`.

## Dependencies

Phase 03 `RepositoryIntelligence`. Section 01 `EvidenceRecord`.

## Atomic Implementation Tasks

1. `SessionRepoSnapshot` Pydantic model with caps and `truncated`.
2. `build_snapshot(ri) -> SessionRepoSnapshot` — status, summary, map, manifests; fail closed on stale/unindexed.
3. In-process cache keyed by `(repo_root, catalog_hash)`.
4. Manifest parser with size limits; missing files are omission, not error.
5. Unit tests: caps; language vs framework; FastAPI from fixture `pyproject` **or** documented skip if the corpus has no manifest; stale index raises.
6. Integration test against the Phase 03 benchmark corpus: services include `auth` / `billing` / `storage` / `web` / `shared`.
7. Extend `tests/contract/test_repo_intel_boundary.py` `CALLER_TREES` to include `packages/requirements_engine`.

## Manual Testing Procedure

1. Print snapshot JSON for the benchmark corpus. Confirm it is small and has no file bodies.
2. Confirm `languages` is `["python"]`, not `["FastAPI"]`.
3. Touch a corpus file without reindexing; confirm snapshot build fails closed.

## Expected Demo

One printed snapshot plus `catalog_hash`, `token_estimate`, and `truncated`.

## Acceptance Criteria

- [ ] Snapshot is generated **once** per session and reused.
- [ ] No LLM is used to generate it.
- [ ] No new RI public method.
- [ ] Size caps are tested.
- [ ] Stale/unindexed fails closed.
- [ ] Requirements engine does not import RI internals.

## Risks

- **Risk:** Treating snapshot `tech_stack` as frameworks. **Mitigation:** field naming (`languages`) and tests.
- **Risk:** Snapshot grows with service count. **Mitigation:** caps + `other_service_count`.

## Future Improvements

- Phase 11: shard-level L4 summaries replace a monorepo-wide `_all_symbols` load.
- Phase 12: replace in-degree map with personalized PageRank.
- Optional: index manifests in RI so Phase 04 does not read disk. Not required now.

## Research Opportunities

Whether `file_count`-conditioned cap tables beat a single cap — measure once a >10k corpus exists.
