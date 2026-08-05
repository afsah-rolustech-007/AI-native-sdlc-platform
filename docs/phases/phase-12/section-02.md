# Section 02 — Aider-Style PageRank Repo Map

## Objective

Implement the real Aider-style PageRank repo map (§H.2): compute PageRank over the codebase's import/reference graph, and inject a top-K files/symbols map as Level 0.5 context — replacing Phase 03 §06's simple raw-in-degree placeholder.

## Why It Exists

Phase 03 explicitly deferred this, using in-degree as a documented stand-in. PageRank differs meaningfully from raw in-degree: a file referenced by a few highly-important files should rank higher than one referenced by many unimportant ones — exactly the signal that matters for giving an agent a token-efficient sense of "what matters most" before it retrieves anything specific.

## Expected Architecture

`packages/repo_intel/summaries/repo_map.py` computes PageRank over the dependency graph (now Neo4j-backed at scale, Phase 11 §03 — using Neo4j's Graph Data Science library if available, or exporting the relevant subgraph for offline PageRank computation via NetworkX/`networkx.pagerank` if that's simpler and sufficiently performant at the per-shard scale this needs to run at). `get_aider_repo_map(scope)` (§G.6's interface, already declared since Phase 03 §06) is re-implemented against real PageRank scores, producing a top-K files/symbols map with signatures, injected as Level 0.5 context (after architecture summary, before progressive expansion) per §H.2's exact injection order.

## Dependencies

Phase 11 §03 (Neo4j graph to compute PageRank over at scale), Phase 03 §06 (the interface/placeholder being replaced).

## Atomic Implementation Tasks

1. Implement PageRank computation over the import/reference graph, scoped per-shard (running PageRank over the full federated graph at once is unnecessary and expensive — scope it to the relevant shard(s) for a given query, consistent with Phase 11's federation design).
2. Implement `get_aider_repo_map(scope)` producing the top-K files/symbols by PageRank score, with signatures (reusing Phase 03 §01's Tree-sitter symbol data), targeting the blueprint's stated ~1,000–3,000 token cost.
3. Wire the repo map into every agent's context assembly at Level 0.5, per §M.2's context injection order (architecture summary, then repo map, then Phase Handoff Packet, then task-specific retrieved context) — update the system prompt template (Phase 05 §03) to reflect this ordering explicitly if it wasn't already structured this way.
4. Unit tests: PageRank scores are correctly computed and produce a sensible top-K ranking for the fixture/demo repo (spot-checked against known important files, e.g., a central config or shared utility module should rank highly).
5. Replace all call sites still using Phase 03 §06's placeholder implementation.

## Manual Testing Procedure

1. Compute the repo map for the demo repo and manually review the top-K files for plausibility (do the genuinely central/important files rank highly?).
2. Compare the PageRank-based ranking against Phase 03's raw in-degree placeholder ranking for the same repo, noting where they differ and why.
3. Confirm the repo map's token cost falls within the blueprint's stated ~1,000–3,000 token target.

## Expected Demo

A side-by-side printed comparison: Phase 03's placeholder ranking vs. this section's real PageRank ranking for the same repo scope, with a brief explanation of any meaningful difference (e.g., a widely-but-shallowly-referenced file dropping in rank versus a deeply-central one rising).

## Acceptance Criteria

- [ ] PageRank is computed correctly over the real dependency graph (verified by spot-checking known-important files rank appropriately).
- [ ] `get_aider_repo_map()` output token cost falls within the ~1,000–3,000 token target.
- [ ] The repo map is injected at Level 0.5, in the correct order, across all agents built in Phases 05–10.
- [ ] Phase 03 §06's placeholder implementation is fully replaced, with no remaining call sites.

## Risks

- **Risk:** PageRank computed over a very large federated graph could itself become an expensive operation if not properly scoped per-shard. **Mitigation:** the explicit per-shard scoping decision (task 1) is the direct mitigation — measure computation time and treat any surprising cost as a signal to narrow scope further, not to abandon PageRank for something cruder.

## Future Improvements

- Caching PageRank scores with incremental updates (rather than full recomputation) tied to Phase 03 §05's incremental indexing triggers — a reasonable optimization once real recomputation cost is measured.

## Research Opportunities

Compare agent performance (design/implementation quality, first-pass acceptance rate) with the repo map present versus absent, on a controlled set of tasks — directly quantifies the map's value, beyond just "it's a proven technique elsewhere" (Aider's own reported results, cited by the blueprint, but worth validating in this platform's specific agent context).
