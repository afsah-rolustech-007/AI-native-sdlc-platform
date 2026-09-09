# Section 05 — Working-Tree Incremental Indexing

## Objective

Keep Repository Intelligence aligned with the **local working tree** (files currently on disk under `repo_root`, including uncommitted edits) without rebuilding every index on every edit. Hit the Phase 03 latency target: incremental update **under 10 seconds for a typical 1–20 file working-tree change** at a few hundred to low-thousands of files.

Git commits, remotes, branches, pull/push, and git hooks are **not** this section's mechanism.

## Why It Exists

Full re-indexing on every save does not scale past a trivial fixture, and a git-commit-based index would lie about the code the engineer (and later, agents) just wrote. This section is what makes RI a trustworthy reflection of **disk**, which every downstream agent implicitly assumes.

## Expected Architecture

`packages/repo_intel/indexers/catalog.py` owns discovery, ignore rules, and the `indexed_files` catalog. `packages/repo_intel/indexers/incremental.py` computes a content-hash diff against that catalog and applies **scoped** updates to Tree-sitter, Zoekt, NetworkX, and pgvector.

No filesystem watcher. No post-commit hook. No event bus.

### 1. Initial indexing

**Discovery.** `index <repo_root>` (CLI and/or `RepositoryIntelligence.index(repo_root)`). `repo_root` is an explicit absolute path from config/`RI_REPO_ROOT`, not inferred from `git rev-parse`. A git repo is **not** required.

**Walk.** Recurse from `repo_root`. Include source files for languages Tree-sitter supports in this phase (start Python + TypeScript; additive later).

**Exclude** (deny list, documented in code):

- `.git/`
- `node_modules/`, `.venv/`, `venv/`, `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`
- `dist/`, `build/`, `*.egg-info/`
- obvious binaries / non-text (by extension) and files over a size cap (~1 MiB)

If a `.gitignore` exists, apply it as an **ignore-file format** (same patterns the engineer already uses). That is convenience, not “git is the source of truth.” Untracked, un-ignored files **are** indexed.

**First index.** Full walk → parse/index every eligible file into all four stores → write `indexed_files` and a repo-level snapshot.

**Catalog metadata (what “version” we indexed):**

| Field | Role |
|---|---|
| `relative_path` | Identity of the file in the tree |
| `content_hash` | SHA-256 of file bytes — **authority** for “this is what we indexed” |
| `size_bytes` | Debug / optional prefilter later |
| `mtime_ns` | Hint only — **not** freshness authority |
| `last_indexed_at` | When this path was last successfully indexed |
| `parse_status` | ok / skipped / parse_error |

Repo snapshot: `repo_root`, `snapshot_id`, `indexed_at`, `file_count`, `catalog_hash` (hash of sorted `(path, content_hash)` pairs). **Not** a git commit SHA.

### 2. Change detection — chosen mechanism

| Option | Verdict for MVP |
|---|---|
| Filesystem mtimes | Rejected as authority (copy, some editors, containers, `touch`) |
| Content hashes (SHA-256 of bytes) | **Chosen** |
| Filesystem watcher | Deferred — extra process, missed events, no strong need |
| Explicit `reindex` command | **Chosen as the trigger** (hashes decide *what* changed) |
| Git diff | Rejected as source of the changed-file set (misses uncommitted work) |

**On `reindex`:** walk eligible files, SHA-256 every file, compare to the catalog. At hundreds–thousands of files this is cheap compared to Tree-sitter/embed. Do **not** trust mtime to skip hashing in v1 (simpler, reliable). mtime short-circuit is a later optimization if hashing ever shows up in profiles.

### 3. Incremental re-index (do not rebuild every index for every change)

Walk vs catalog produces: **created**, **modified** (hash differs), **deleted** (in catalog, missing on disk). **Rename** = delete old path + create new path (same-hash rename detection is **DEFERRED**).

Then update **only the affected paths**. Do **not** expand to 1–2 hop dependents for re-indexing (that expansion is a **query** via `get_impact_set`, not an index job).

| Event | Tree-sitter | Zoekt | NetworkX | pgvector |
|---|---|---|---|---|
| **File created** | Parse; insert symbols | Add file (or include in scoped/full Zoekt rebuild — see below) | Add nodes/edges extracted from **this** file | Embed new symbol chunks |
| **File modified** | Delete this path's symbols; re-parse; insert | Update this file | Drop this file's **outgoing** edges; re-extract from this file. Incoming edges from *other* files stay until those files change | Re-embed chunks whose **chunk** `content_hash` changed; delete chunks for removed symbols |
| **File deleted** | Delete symbols for path | Remove file | Remove this file's nodes and incident edges | Delete embeddings for path |
| **File renamed** | Treat as delete + create | Same | Same | Same (rewrite `file_path` only if we later add same-hash rename; not required now) |
| **Symbols in the file change** | Yes (it's a modify) | Yes if text changed | Yes for this file's edges | Yes for changed chunks only |
| **Imports/deps in the file change** | Yes (AST includes imports) | Yes if text changed | **Yes — this is the graph update for that file** | Only if chunk text hash changed (usually yes, because the file text changed) |
| **“Semantic embedding of this file should change”** | n/a | n/a | n/a | Only if chunk `content_hash` changed |

**Zoekt MVP compromise:** if per-file Zoekt updates are awkward, a **full Zoekt rebuild of the working tree** after a small hash-diff is allowed. At this scale that is still cheap. Tree-sitter, NetworkX, and pgvector **must not** full-rebuild just because Zoekt did. Document the choice in code comments.

### 4. Scheduling (when indexing runs)

Prefer explicit triggers over a permanent background watcher.

| Trigger | Who | Behavior |
|---|---|---|
| `index` | Human / setup script | First full index (or after catalog wipe) |
| `reindex` | Human / script after local edits | Hash walk + scoped incremental |
| `reindex_paths(paths)` | Future agents after they write files (API exists now; Phase 05+ must call it) | Incremental on those paths (still hash-verify) |
| Before retrieval | RI API | **Does not** auto-embed on every query. If stale → `StaleIndexError` (see §5). Optional `refresh=True` runs `reindex` then the query |
| Git hook / inotify / nightly full job | — | **DEFERRED** |

Lifecycle: `unindexed` → `index` → `fresh` → (disk edits) → `stale` (per-file in catalog vs tree; API treats **any** stale eligible file as blocking) → `reindex` → `fresh`.

### 5. Staleness

**Compared:** catalog `(relative_path, content_hash)` vs current eligible working tree (same walk/ignore rules).

**Detected as stale:**

- hash mismatch (modified)
- path in tree not in catalog (created)
- path in catalog not in tree (deleted)

**Granularity:** detection is **per-file**. The repo is not one boolean, but retrieval still **blocks if any eligible file is stale** — mixed fresh/stale is unsafe to serve as “current code.”

**On retrieval while stale:** fail-closed. Raise `StaleIndexError` listing stale paths. Do **not** return results as if current. Do **not** return empty as if “no hits.” Caller runs `reindex` / `reindex_paths` or `refresh=True`.

Cheap check: same hash walk as `reindex` (at MVP scale this is fine). Do not use commit SHA or “max mtime of the repo.”

### 6. Dependency propagation (`A.py` imports `B.py`; `B.py` changes)

**Update immediately:** `B.py` on all four stores (row in the table above).

**Leave unchanged:** `A.py` symbols, `A.py` Zoekt posting, `A.py` embeddings, `A.py`'s outgoing edges. `A.py`'s text did not change. The import edge `A → B` remains valid until `A.py` is reindexed (and it does not need to be).

**Graph query-time:** `get_impact_set(["B.py"])` still finds `A.py` via existing edges. That is a **read**, not a reason to re-embed `A`.

**Do not** regenerate `A.py` embeddings because `B` changed. Cross-file embedding invalidation is **DEFERRED** (Phase 11+ if a real eval shows it's needed).

**Known limitation (document, don't “fix” in Phase 03):** if `B` renames a function, `A`'s stored *call* edge may still name the old symbol until `A.py` is reindexed. Import-level impact is enough for Phase 07's first use.

### 7. Performance

Target: a few hundred to low-thousands of files.

- Hash walk all eligible files (cheap).
- Parse / graph-extract / embed **only** paths whose file hash changed (plus deletes).
- Skip pgvector writes when chunk `content_hash` is unchanged even inside a modified file (e.g. untouched functions).
- Do not BFS-expand the re-index set.
- Keep the &lt;10s target, measured on a **1–20 file working-tree change**, not a commit.

## Dependencies

Sections 01–04 (each indexer must support **scoped** update for a path list: replace/delete/insert — not only `index_everything()`). Section 03's graph is **not** used to expand the re-index set.

## Atomic Implementation Tasks

1. Implement `catalog.py`: walk, ignore rules, SHA-256, `indexed_files` + snapshot read/write, `diff_working_tree() -> {created, modified, deleted}`.
2. Implement `incremental.py`: apply the per-event matrix above; log/count files actually re-processed (for the “untouched files were not re-parsed” check).
3. Implement `StaleIndexError` and `index_status()` / `assert_fresh()` used by Section 06's API.
4. Implement CLI: `index`, `reindex`, optional `reindex_paths`. **No** `post_commit_hook.sh` in this phase.
5. Benchmark: edit 1–20 files on disk (no commit), time `reindex`, assert &lt; 10s; assert unrelated files were not re-embedded/re-parsed.

## Manual Testing Procedure

1. `index` the fixture **directory** (git optional).
2. Edit a file on disk without committing. Call a retrieval method → expect `StaleIndexError`.
3. `reindex`, time it, query the edited symbol/string — index matches disk.
4. Confirm logs/counters: only the changed path(s) were re-parsed/re-embedded.
5. Delete a file, `reindex`, confirm it disappears from symbols/search.

## Expected Demo

Timed `reindex` after a small **uncommitted** edit: “N files re-indexed in X.XXs” with X &lt; 10, then a query that proves the index matches the working tree (not HEAD).

## Acceptance Criteria

- [ ] Change detection is content-hash vs working tree — no git diff, no hook required.
- [ ] Incremental path updates Tree-sitter + graph + pgvector for changed files only; unrelated files are not re-processed.
- [ ] Measured latency &lt; 10s for a 1–20 file working-tree change.
- [ ] Retrieval while stale raises `StaleIndexError` (fail-closed), never silent stale answers.
- [ ] `A.py` is not re-embedded solely because `B.py` (imported by A) changed.
- [ ] Uncommitted new/modified files are indexed after `reindex`.

## Risks

- **Risk:** Humans (and later agents) forget to `reindex`. **Mitigation:** fail-closed `StaleIndexError` on retrieval, not a background watcher and not a git hook. Phase 05+ must call `reindex_paths` after writes.
- **Risk:** Zoekt full rebuild hides a “we re-indexed the world” smell. **Mitigation:** still hash-diff first; Tree-sitter/pgvector remain scoped; document Zoekt rebuild as an MVP compromise.

## Future Improvements (DEFERRED)

- Filesystem watcher / always-on daemon
- Git post-commit hooks, git-diff as an *accelerator* (never as SoT)
- Nightly full re-index job
- Same-hash rename detection
- Re-index 1–2 hop dependents / re-embed importers
- Remote repos, branches, multi-developer sync
- Distributed index, event bus

## Research Opportunities

Log re-index latency vs number of changed files vs tree size now, so Phase 11 has an empirical curve — not a git-commit curve.

---

## Implementation (as built)

### Modules

| Module | Role |
|---|---|
| `catalog.diff_snapshots(snapshots, catalog, scope=None)` | Pure function: working-tree hashes vs `indexed_files` → `CatalogDiff`. No disk, no DB, unit-tested directly. `scope` limits deletes to a path subset so `reindex_paths` does not report the rest of the tree as deleted. |
| `catalog.read_paths(paths)` | Targeted read for `reindex_paths` — same eligibility rules, no whole-tree walk. |
| `symbol_store.list_catalog_hashes` / `replace_file_index` | Diff input, and per-path replace (delete cascades this path's symbols, then reinsert). |
| `indexers/incremental.IncrementalIndexer` | Orchestrates `index` / `reindex` / `reindex_paths` / `status` / `assert_fresh` / `hydrate_graph`. |

### One parse per changed file

`_parse_once` runs Tree-sitter exactly once per created/modified file and shares the
result three ways: symbols → Postgres, `(symbols, tree)` → `NetworkXClient.replace_file_parsed`,
`(symbols, source_text)` → `chunks_from_symbols` → `PgvectorClient.apply_chunks`.
Unchanged files are never read past their hash. Inside a changed file, chunks whose
`content_hash` matches the stored row are counted as `chunks_skipped_unchanged` and
never re-embedded.

A file that fails to parse is recorded with `parse_status="parse_error"`, keeps its
catalog row (so it is not perpetually stale), contributes no symbols or chunks, and
has its outgoing graph edges dropped. One bad file never aborts a run.

### Commit order and failure semantics

1. Parse changed files.
2. Rebuild Zoekt (full rebuild — the documented MVP compromise) **before** the DB commit,
   so the catalog never claims a lexical index that does not exist.
3. One transaction: embeddings → symbol/catalog replace → deletes → repo snapshot → commit.
   Embedding happens before any write, so a provider outage leaves the previous index intact.
4. Patch the in-memory graph last; it is RAM-only and rebuildable.

Any failure rolls the transaction back and raises `RepoIntelError`. A partial reindex is
never durable: there is no state where a catalog row exists without its vectors. The tree
simply stays `stale`, and Section 06 keeps refusing to read.

Missing Zoekt binaries are logged as a warning and do not fail indexing — lexical search
itself still fails closed with `ZoektNotIndexedError`. A Zoekt rebuild that *fails* does
abort the run, leaving the previous shards in place.

### Freshness

`status()` walks the tree, diffs, and returns `IndexStatus(state=unindexed|fresh|stale)`
with the stale paths. `assert_fresh()` raises `StaleIndexError` for both `stale` and
`unindexed` — a never-indexed tree is not silently "fresh and empty".

`NetworkXClient` lives in process memory, so a restart loses it while Postgres and Zoekt
stay fresh. `hydrate_graph()` rebuilds it on the first graph query after the freshness
check passes; it is not part of the stale/fresh contract.

### CLI

`scripts/ri_index.py status|index|reindex [PATH ...] [--repo-root R] [--rebuild] [--live]`.
`index --rebuild` wipes this repo's rows and starts over; plain `index` is `reindex`.

### Known limitation carried forward

A symbol that is deleted from a file but still *called* by another file survives in the
graph as a dangling call target, because Section 03 keeps referenced nodes so the calling
file does not need re-parsing. That is an accurate unresolved reference, not stale data.
