# Section 01 — Domain Shard Partitioning & Boundary Validation

## Objective

Partition a large corpus into domain shards aligned to service/team-ownership boundaries, validated against the L2 dependency graph (not directory structure alone) per §G.4 — a boundary is valid only if cross-boundary edge count is low relative to within-shard edge count.

## Why It Exists

This is the section that determines whether federation actually helps or just adds complexity: shards drawn along the wrong lines (e.g., naive directory-based splitting of a tightly-coupled component) would create more cross-shard query traffic than they save, defeating the purpose. The blueprint is explicit that boundaries must be validated empirically against the dependency graph, not assumed from folder layout.

## Expected Architecture

`packages/repo_intel/sharding/boundary_analysis.py` computes, for a proposed partition (initially derived from directory/service-naming conventions as a starting hypothesis), the ratio of cross-boundary to within-shard edges using Phase 03's dependency graph data. A validation loop adjusts the proposed partition (merging tightly-coupled directories into one shard, splitting loosely-coupled ones) until the ratio meets a defensible threshold (define and document this threshold explicitly — it's a genuine judgment call, not a number the blueprint prescribes numerically).

## Dependencies

Phase 03 §03 (dependency graph data to validate against).

## Atomic Implementation Tasks

1. Implement a starting-hypothesis partitioner (directory/service-naming-convention based) for the chosen large corpus.
2. Implement cross-boundary vs. within-shard edge ratio computation against the real dependency graph.
3. Implement an iterative refinement loop: identify the worst-offending boundary (highest cross-boundary edge ratio), attempt a merge/split adjustment, recompute, repeat until the ratio stabilizes below the documented threshold or no further improvement is found.
4. Document the final threshold choice and the refinement process's outcome (which naive boundaries were wrong, and why) — this is genuinely interesting, worth recording in `docs/decisions/`.
5. Test: for a corpus with at least one deliberately-known tightly-coupled pair of "services" (if using a synthetic/assembled corpus, construct this deliberately), confirm the refinement process correctly merges them into one shard rather than leaving them split.

## Manual Testing Procedure

1. Run the starting-hypothesis partitioner and print the initial cross-boundary edge ratios per proposed shard boundary.
2. Run the refinement loop and observe which boundaries get adjusted.
3. Manually review the final shard assignment for plausibility against your own understanding of the corpus's real architecture.

## Expected Demo

A before/after comparison: the naive directory-based partition's cross-boundary edge ratios vs. the refined, dependency-graph-validated partition's ratios — showing a measurable improvement.

## Acceptance Criteria

- [ ] Shard boundaries are validated against real dependency-graph data, not assumed from directory structure alone.
- [ ] The refinement process demonstrably improves (lowers) cross-boundary edge ratios versus the naive starting hypothesis.
- [ ] At least one deliberately-constructed tightly-coupled case is correctly merged into a single shard by the refinement process.

## Risks

- **Risk:** Some real codebases genuinely don't have clean shard boundaries — the blueprint's own closing line flags this explicitly as something to verify ("whether your repositories have clean existing shard boundaries or will need manual definition," §G.4/closing note). **Mitigation:** if the refinement process fails to converge to a reasonable ratio for a given corpus, that's a valid and important finding to document, not a bug to force-fix — some monoliths may need manual shard definition by a human with real architectural knowledge, and the tooling should support that as a fallback (accept a human-provided partition as an alternative input).

## Future Improvements

- Semi-automated boundary suggestion with human review/override — a reasonable production feature once the algorithmic approach's limitations are well understood.

## Research Opportunities

This section is inherently research-heavy (per `roadmap.md` §3): the "right" cross-boundary ratio threshold, and whether a purely graph-theoretic approach (e.g., community detection algorithms like Louvain) outperforms the iterative refinement approach described here, are both open, worth experimenting with using real corpus data once available.
