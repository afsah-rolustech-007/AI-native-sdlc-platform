# Section 02 — Aider-Style PageRank Repo Map

## Objective

Implement the real Aider-style **Personalized PageRank** repo map (§H.2): from task goal/input → seed set → PPR over the import/reference graph → top-K files+signatures as Level 0.5 context — replacing Phase 03 §06's simple raw-in-degree placeholder.

## Why It Exists

Phase 03 deferred this, using in-degree as a stand-in. Global “most important files in the repo” is the wrong product: agents need files relevant to **this** goal. Personalized PageRank teleports back to a task seed set, so rank mass concentrates in the structural neighborhood of the ticket/grep hits/prior edits — not on globally popular utilities. That is the signal that gives a token-efficient “what matters for this task” before any body retrieval.

## Expected Architecture

`packages/repo_intel/summaries/repo_map.py` implements §H.2 end-to-end:

1. **SeedCollection** from Context Builder inputs (explicit paths, grep/glob hits, prior-wave/WCP files, impact/localisation hints, L0 fallback) with source weights (§H.2.2).
2. **Personalized PageRank** on the per-shard dependency subgraph (Neo4j GDS if available, else NetworkX `pagerank(personalization=v)`), α=0.85 (§H.2.3).
3. **Render** top-K files packed to `budget_tokens` with Tree-sitter signatures only (§H.2.4).
4. **`get_aider_repo_map(...)`** returns `RepoMap`; Context Builder injects it as L0.5 per §H.2.5 / §M.2 (after architecture summary, before Phase Handoff Packet and progressive expansion).

Cache key: `(shard_graph_version, frozenset(seeds), α, agent_phase)`. Rebuild on new wave, new WCP targets, or graph version bump — not on every tool call.

## Dependencies

Phase 11 §03 (Neo4j graph at scale), Phase 03 §06 (interface/placeholder being replaced), Phase 05 context assembly / system prompt template (injection order).

## Atomic Implementation Tasks

1. Implement `SeedCollection` builder (or accept pre-built seeds from Context Builder) with S1–S5 sources and weights exactly as §H.2.2.
2. Implement PPR over the import/reference graph, scoped to shard(s) covering the seeds (+ k-hop closure) — never full federated graph.
3. Re-implement `get_aider_repo_map(scope, *, seeds, budget_tokens, agent_phase, ...)` to return packed top-K files/symbols by PPR score (~1,000–3,000 tokens default; respect phase budgets).
4. Wire Context Builder so every agent prompt gets L0.5 in §M.2 order; workers personalize on WCP `target_files`; Design/Impl Manager use task-level seeds; QA uses diff + impact seeds (§H.2.5 table).
5. Add score cache keyed by graph version + seeds; invalidate from Phase 03 §05 incremental index triggers.
6. Unit tests: known fixture seeds pull the expected neighborhood into top-K (not merely global hubs); token estimate stays in band; placeholder call sites removed.

## Manual Testing Procedure

1. Pick a concrete demo goal (e.g. “add revoke_session to AuthService”). Build seeds from goal text + one grep sweep; print top-K and confirm auth/session modules dominate over unrelated high-degree utils.
2. Compare three rankings on the same repo: Phase 03 in-degree, global PageRank (no personalization), personalized PageRank — note where PPR correctly promotes seed-neighborhood files.
3. Confirm L0.5 token cost within budget; confirm worker map differs from manager map when WCP targets are a subset.

## Expected Demo

Side-by-side: (a) in-degree placeholder, (b) global PageRank, (c) personalized PageRank for one task seed set — with a one-paragraph explanation of which files moved and why that helps the agent.

## Acceptance Criteria

- [ ] PPR uses a non-uniform personalization vector derived from task seeds (§H.2.2), not uniform global PageRank alone.
- [ ] `get_aider_repo_map()` output token cost falls within the configured budget band (~1,000–3,000 default).
- [ ] L0.5 is injected in the correct order across agents from Phases 05–10; workers seed from WCP targets.
- [ ] Phase 03 §06 placeholder is fully replaced; cache invalidates on graph version bump.
- [ ] Spot-check: seed-neighborhood files outrank unrelated global hubs for the demo task.

## Risks

- **Risk:** PPR over a large shard is expensive if under-scoped. **Mitigation:** seed + k-hop closure only; measure; narrow k before abandoning PPR.
- **Risk:** Noisy grep seeds pollute the map. **Mitigation:** lower S2 weight, cap seed count at 12, prefer S1/S3 when present.

## Future Improvements

- Incremental PPR updates tied to Phase 03 §05 index triggers (avoid full recompute).
- Optional symbol-level PPR for dense files once file-level packing is stable.

## Research Opportunities

Ablate: no map vs global PageRank vs personalized PageRank on the same task set — measure first-pass module localisation accuracy and tokens/task (supports Phase 12’s ≥40% token reduction gate).
