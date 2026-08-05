# Section 05 — Git-Diff Incremental Indexing

## Objective

Implement git-hook-triggered incremental re-indexing scoped to changed files and their 1–2 hop dependents (§G.5), replacing the "rebuild everything" approach used for manual testing in Sections 01–04, and hit the blueprint's explicit target: incremental update latency under 10 seconds for a typical 1–20 file commit.

## Why It Exists

Full re-indexing on every change does not scale past a trivial fixture repo, and — more importantly for solo-engineer velocity — makes the manual test loop from Sections 01–04 painfully slow to iterate on. This section is what makes Repository Intelligence a *live*, trustworthy reflection of the current repo state rather than a one-time snapshot, which every downstream agent implicitly assumes.

## Expected Architecture

`packages/repo_intel/indexers/incremental.py` hooks into git (`post-commit` hook, or a polling/watch-based fallback for environments without hook access) to compute the diff since the last indexed commit, determines the changed file set, expands it to 1–2 hop dependents via Section 03's graph (`get_dependents`), and re-runs Sections 01/02/04's indexing pipelines scoped to only that file set. A nightly full re-index (mentioned in §G.5 as a "drift-safety net") is scheduled as a Phase 00-worker job — implemented here since it's the natural conclusion of this section's work, even though it's technically a scheduling concern.

## Dependencies

Sections 01–04 (all three indexes must support scoped/partial re-run, not just full-repo rebuild), Section 03 (dependent-expansion needs the graph).

## Atomic Implementation Tasks

1. Implement `get_changed_files(since_commit) -> list[str]` via `git diff --name-only`.
2. Implement dependent-expansion: `changed_files ∪ get_dependents(f, depth=2) for f in changed_files`.
3. Implement scoped re-run for Tree-sitter (re-parse only the expanded file set, update/replace their `Symbol` rows), Zoekt (incremental index update if supported natively, else scoped rebuild), and pgvector (re-embed only chunks whose `content_hash` changed — this is where Section 04's `content_hash` field pays off).
4. Implement the git post-commit hook script (`scripts/post_commit_hook.sh` per §Q) invoking the incremental indexer.
5. Implement the nightly full re-index as an ARQ scheduled job (Phase 00's worker).
6. Implement staleness detection for L4-equivalent cached data (architecture summary, once it exists in Section 06) via content-hash + dependency-hash keys per §G.5 — wire the mechanism now even if the summary itself is built in Section 06.
7. Benchmark test: make a controlled 1–20 file change to the fixture (or a larger sample) repo, time the incremental re-index, assert < 10s.

## Manual Testing Procedure

1. Make a small, realistic commit to the demo repo (e.g., rename a function used in 3 other files).
2. Run the incremental indexer and time it.
3. Query `get_symbol_signature` for the renamed function and confirm it reflects the new name; query a dependent file's symbols to confirm no stale references remain in the index for the changed relationship.
4. Manually verify unrelated, untouched files were *not* re-processed (e.g., via a log/counter of files touched by this run).

## Expected Demo

Terminal output: a timed run of the incremental indexer after a small commit, printing "N files re-indexed in X.XXs" with X < 10, followed by a query proving the index reflects the change.

## Acceptance Criteria

- [ ] Incremental indexing correctly scopes to changed files + 1–2 hop dependents, not the full repo.
- [ ] Measured latency is under 10 seconds for a 1–20 file commit on the benchmark repo — this is the blueprint's explicit Phase 3 completion criterion and must be measured, not assumed.
- [ ] Nightly full re-index job is scheduled and runs successfully at least once in testing (can be manually triggered for the demo rather than waiting for a real nightly schedule).
- [ ] Content-hash-based staleness detection correctly identifies unchanged chunks and skips re-embedding them.

## Risks

- **Risk:** Git hook installation is per-clone and easy to forget/misconfigure, silently leaving the index stale. **Mitigation:** the nightly full re-index exists specifically as this safety net (per §G.5) — document clearly that hooks are an optimization, not the sole freshness mechanism.

## Future Improvements

- Sharded, parallel incremental indexing across domain shards — Phase 11.

## Research Opportunities

Measure how re-index latency scales as fixture repo size grows, to build an early empirical model of what "1M files" will require in Phase 11 — cheap to start collecting this data now.
