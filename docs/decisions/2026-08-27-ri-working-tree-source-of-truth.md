# Decision: Repository Intelligence source of truth is the local working tree

**Date:** 2026-08-27  
**Status:** Accepted for Phase 03 MVP  
**Affects:** Phase 03 (`docs/phases/phase-03/`), `docs/architecture.md` §4.1, `final_plan.md` §G.2 / §G.5 / Part C Phase 3

## Context

The blueprint described L0 as “raw files + git metadata” updated “real-time via git hooks,” and Phase 3 completion as “incremental update &lt; 10s for a 20-file **commit**.” For the current MVP that is the wrong source of truth: the product must retrieve the files the engineer (and later, agents) just wrote, including uncommitted changes.

## Decision

Index the **local working tree** under an explicit `repo_root`. Change detection is **SHA-256 of file bytes** vs an `indexed_files` catalog. Triggers are explicit `index` / `reindex` / `reindex_paths` (plus fail-closed `StaleIndexError` on retrieval). Git hooks, git diff, remotes, branches, and watchers are deferred.

Full lifecycle, per-index update matrix, and dependency-propagation rules: `docs/phases/phase-03/section-05.md`.
