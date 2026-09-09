# Section 06 — RepositoryIntelligence API & Retrieval Precision Benchmark

## Objective

Assemble Sections 01–05 behind the single `RepositoryIntelligence` interface (§G.6, MVP subset — structural + semantic methods; hybrid RRF fusion and historical/episodic methods are stubbed or deferred per what data exists at this phase), add the AST-generated architecture summary (§G.7), and build the held-out labeled retrieval benchmark that produces this phase's numeric completion criterion. Retrieval reads the **working-tree-backed** indexes from Sections 01–05; it must fail-closed on stale catalog (`StaleIndexError`) rather than serving last-commit or last-index data as if current.

## Why It Exists

No agent, from Phase 04 onward, is allowed to touch the graph DB, vector store, or Zoekt client directly (per §G.1's design decision) — this section is what makes that rule enforceable, by giving agents the *only* door in. The benchmark is what turns "retrieval feels pretty good" into a number the rest of the roadmap can trust and later compare against (Phase 11's "within 5 points of Phase 3 baseline at scale" criterion directly depends on this baseline existing).

## Expected Architecture

`packages/repo_intel/api.py` implements the `RepositoryIntelligence` class exposing (at this phase): `index` / `reindex` / `reindex_paths` / `index_status` (Section 05), `get_callers`, `get_callees`, `get_dependencies`, `get_dependents`, `get_impact_set`, `get_symbol_signature`, `get_symbol_body`, `get_file_structure` (structural, Section 01/03), `search_concepts`, `find_similar_implementations` (semantic, Section 04), `get_architecture_summary` (new, Section 06), and `get_aider_repo_map` as a stub returning a simple heuristic (full PageRank implementation is Phase 12/§H.2 — the method exists in the interface now so agents can be written against its signature, but its Phase 3 implementation can be a simpler placeholder, documented as such). Every read method runs Section 05's freshness check first (unless the caller passed `refresh=True`, which reindexes then reads). `get_regression_history`, `get_design_decisions`, `get_change_frequency`, and `find_relevant_context` (hybrid RRF) are declared in the interface but raise `NotImplementedError` until Phase 06 (episodic data) and Phase 12 (fusion) respectively — this makes the *full* target interface visible from Phase 3 onward without faking capabilities that don't exist yet. Historical methods that would need git history (`get_change_frequency`, etc.) stay unimplemented; Phase 03 does not grow a git-history indexer.

## Dependencies

Sections 01–05.

## Atomic Implementation Tasks

1. Implement `RepositoryIntelligence` as the single public class wrapping Sections 01–05's clients — no other module imports those clients directly from this point forward (enforce via CI grep, same pattern as Phase 02's provider-SDK check).
2. Implement `get_architecture_summary()` per §G.7 — an AST-generated (never LLM-generated) JSON summary: services/modules, entry points, key symbols, dependencies, tech stack, shared modules, database entities, API boundaries. Derive this entirely from Sections 01/03's symbol and graph data.
3. Implement a placeholder `get_aider_repo_map(scope)` (e.g., top-N files by raw in-degree from the dependency graph, as a simple stand-in for PageRank) with a clear docstring noting Phase 12 replaces this with the full Aider-style PageRank algorithm.
4. Build `tests/benchmark/retrieval_precision.py`: hand-label ~20–30 queries against the fixture/demo repo (mix of "find symbol," "find caller," "find similar implementation," "find by concept" query types) with known correct answers; compute precision@5 for each query type and overall.
5. Run the benchmark, iterate on any retrieval gaps found (this is expected — treat sub-90% results as signal to improve chunking/query construction in Sections 02/04, not to lower the bar).
6. Document the final benchmark results and methodology in `docs/decisions/` (or a `tests/benchmark/README.md`) so Phase 11 has a documented baseline to compare against.

## Manual Testing Procedure

1. Run the full benchmark suite and inspect the per-query-type precision breakdown, not just the aggregate.
2. Manually spot-check a handful of the lower-scoring queries to understand *why* (bad chunking? ambiguous query wording? genuine retrieval failure?) before concluding the number is final.
3. Call `get_architecture_summary()` and manually review the JSON output for accuracy against your own knowledge of the fixture/demo repo.

## Expected Demo

This section's demo *is* Phase 03's overall live demo (see Phase 03 README): the benchmark run printing overall precision@5 against the ≥90% target, followed by the incremental re-index timing demo from Section 05 (**uncommitted** working-tree edit, not a commit), followed by a printed `get_architecture_summary()` output.

## Acceptance Criteria

- [ ] `RepositoryIntelligence` is the sole entry point for repo data access — no other module imports Sections 01–05's clients directly (grep-verifiable).
- [ ] Retrieval precision@5 ≥ 90% on the held-out labeled benchmark set — the blueprint's explicit Phase 3 completion criterion.
- [ ] `get_architecture_summary()` output is verified accurate by manual review against the demo repo.
- [ ] Methods not yet implementable at this phase (`find_relevant_context`, historical methods) exist in the interface signature and fail explicitly (`NotImplementedError`), never silently return empty/wrong data.
- [ ] Read methods raise `StaleIndexError` when the working tree has drifted from the catalog; they do not silently serve a stale index.

## Risks

- **Risk:** A benchmark hand-labeled by the same engineer who built the retrieval system risks unconscious bias toward queries the system already handles well. **Mitigation:** write the query list *before* looking at what the system currently returns for them, and include a few deliberately adversarial/ambiguous queries.

## Future Improvements

- Full Aider-style PageRank repo map — Phase 12.
- Hybrid RRF fusion across Zoekt + pgvector + graph expansion — Phase 12.
- Historical/episodic methods (`get_regression_history`, `get_design_decisions`, `get_change_frequency`) — populated once Phase 06+ generates real episodic data.

## Research Opportunities

This benchmark is the first real evaluation artifact in the entire roadmap — consider whether its query taxonomy (by type) generalizes into the Golden Dataset structure Phase 15 will need; reusing the same labeling discipline here saves rework later.

---

## Implementation (as built)

### The four signals stay separate

`packages/repo_intel/api.py` exposes symbol, lexical, semantic, and graph retrieval as
four independent methods. There is **no cross-store fusion** at this phase:

| Signal | Method(s) | Backing store |
|---|---|---|
| symbol | `get_symbol_signature`, `get_symbol_body`, `get_file_structure` | Postgres (Section 01) |
| lexical | `search_codebase` | Zoekt (Section 02) |
| semantic | `search_concepts`, `find_similar_implementations` | pgvector (Section 04) |
| graph | `get_callers`, `get_callees`, `get_dependencies`, `get_dependents`, `get_impact_set` | NetworkX (Section 03) |

Keeping them separate is what makes the benchmark diagnostic: a miss is attributable to
one retrieval signal rather than to a ranking formula. Overlap dedup and `kinds`/`paths`/
`min_score` filtering stay inside pgvector where the spans are known. RRF fusion
(`find_relevant_context`) raises `NotImplementedError` until Phase 12.

### Freshness gate

Every read calls Section 05's whole-tree `assert_fresh()` first and raises `StaleIndexError`
on drift. `refresh=True` reindexes and then reads. Graph reads additionally hydrate the
RAM-only NetworkX graph if this process has not built it yet.

### Deferred methods fail loudly

`find_relevant_context` (Phase 12), `get_regression_history`, `get_design_decisions`, and
`get_change_frequency` (Phase 06+ episodic data) exist with real signatures and raise
`NotImplementedError` naming the phase. They never return empty as if that were an answer.

### Boundary enforcement

`tests/contract/test_repo_intel_boundary.py` parses the AST of everything under `apps/`,
`packages/orchestration/`, `packages/common/`, and `scripts/` and fails if anything imports
`repo_intel.symbol_store`, `repo_intel.indexers.*`, `repo_intel.graph`, or `repo_intel.vector`
directly. Indexing entry points and the section demos are on an explicit allowlist.

### `get_architecture_summary` and `get_aider_repo_map`

`packages/repo_intel/summary.py` derives the §G.7 JSON purely from symbols + import edges —
deterministic and diffable, never LLM-generated. "Service" is the first path segment, which
is a crude but honest proxy for ownership. `get_aider_repo_map` ranks files by raw import
in-degree; Phase 12 replaces it with Aider-style PageRank.

### Benchmark: success@5, not precision@5

`tests/benchmark/` holds a **frozen corpus** (`corpus/`, 14 files across 5 services, including
deliberate semantic near-misses) and **frozen labels** (`queries.json`, 29 queries). Both are
frozen so a label can never be edited to make a run pass.

The metric is **success@5**: a query is a hit when at least one gold answer is in the top 5.
Classic precision@5 is the wrong instrument here — most queries have exactly one correct
answer, so precision@5 is capped at 0.20 and would measure nothing. Success@5 answers the
question that actually matters for an agent: did the right code reach the context window?

Reported per signal and per query type. Run with `make benchmark`, or as part of the suite
via `tests/integration/test_retrieval_benchmark.py`.

**Baseline (deterministic hashing embedder, Zoekt not installed):**

| Scope | success@5 |
|---|---|
| overall | 96.2% (25/26 scored) |
| semantic | 100% (19/19) |
| graph | 86% (6/7) |
| lexical | not scored — Zoekt binaries unavailable on the measuring machine |

The single miss (`g06`) is a labeled-adversarial query: callers reach `DatabasePool.acquire`
through `self.pool`, and Section 03 resolves direct-name calls only. It is a documented
recall limit of attribute-call resolution, kept in the set rather than deleted.

Building this benchmark found one real defect: header-only class chunks were suppressing
their own methods during overlap dedup, because a class row spans the whole class while its
vector is signature + docstring only. Exempting class rows from suppression moved semantic
success@5 from 94% to 100%.
