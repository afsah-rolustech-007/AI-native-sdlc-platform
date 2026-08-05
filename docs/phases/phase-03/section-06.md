# Section 06 — RepositoryIntelligence API & Retrieval Precision Benchmark

## Objective

Assemble Sections 01–05 behind the single `RepositoryIntelligence` interface (§G.6, MVP subset — structural + semantic methods; hybrid RRF fusion and historical/episodic methods are stubbed or deferred per what data exists at this phase), add the AST-generated architecture summary (§G.7), and build the held-out labeled retrieval benchmark that produces this phase's numeric completion criterion.

## Why It Exists

No agent, from Phase 04 onward, is allowed to touch the graph DB, vector store, or Zoekt client directly (per §G.1's design decision) — this section is what makes that rule enforceable, by giving agents the *only* door in. The benchmark is what turns "retrieval feels pretty good" into a number the rest of the roadmap can trust and later compare against (Phase 11's "within 5 points of Phase 3 baseline at scale" criterion directly depends on this baseline existing).

## Expected Architecture

`packages/repo_intel/api.py` implements the `RepositoryIntelligence` class exposing (at this phase): `get_callers`, `get_callees`, `get_dependencies`, `get_dependents`, `get_impact_set`, `get_symbol_signature`, `get_symbol_body`, `get_file_structure` (structural, Section 01/03), `search_concepts`, `find_similar_implementations` (semantic, Section 04), `get_architecture_summary` (new, Section 06), and `get_aider_repo_map` as a stub returning a simple heuristic (full PageRank implementation is Phase 12/§H.2 — the method exists in the interface now so agents can be written against its signature, but its Phase 3 implementation can be a simpler placeholder, documented as such). `get_regression_history`, `get_design_decisions`, `get_change_frequency`, and `find_relevant_context` (hybrid RRF) are declared in the interface but raise `NotImplementedError` until Phase 06 (episodic data) and Phase 12 (fusion) respectively — this makes the *full* target interface visible from Phase 3 onward without faking capabilities that don't exist yet.

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

This section's demo *is* Phase 03's overall live demo (see Phase 03 README): the benchmark run printing overall precision@5 against the ≥90% target, followed by the incremental re-index timing demo from Section 05, followed by a printed `get_architecture_summary()` output.

## Acceptance Criteria

- [ ] `RepositoryIntelligence` is the sole entry point for repo data access — no other module imports Sections 01–05's clients directly (grep-verifiable).
- [ ] Retrieval precision@5 ≥ 90% on the held-out labeled benchmark set — the blueprint's explicit Phase 3 completion criterion.
- [ ] `get_architecture_summary()` output is verified accurate by manual review against the demo repo.
- [ ] Methods not yet implementable at this phase (`find_relevant_context`, historical methods) exist in the interface signature and fail explicitly (`NotImplementedError`), never silently return empty/wrong data.

## Risks

- **Risk:** A benchmark hand-labeled by the same engineer who built the retrieval system risks unconscious bias toward queries the system already handles well. **Mitigation:** write the query list *before* looking at what the system currently returns for them, and include a few deliberately adversarial/ambiguous queries.

## Future Improvements

- Full Aider-style PageRank repo map — Phase 12.
- Hybrid RRF fusion across Zoekt + pgvector + graph expansion — Phase 12.
- Historical/episodic methods (`get_regression_history`, `get_design_decisions`, `get_change_frequency`) — populated once Phase 06+ generates real episodic data.

## Research Opportunities

This benchmark is the first real evaluation artifact in the entire roadmap — consider whether its query taxonomy (by type) generalizes into the Golden Dataset structure Phase 15 will need; reusing the same labeling discipline here saves rework later.
