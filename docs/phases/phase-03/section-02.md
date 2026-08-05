# Section 02 — Zoekt Trigram Search Integration (L0/L1)

## Objective

Stand up Zoekt as the lexical/trigram code search engine (§G.3) — proven over SCIP and over naive `ripgrep`-style scanning in the blueprint's own comparative analysis — and expose it through a `search_codebase` capability.

## Why It Exists

Symbol-aware retrieval (Section 01) answers "what is this symbol" but not "where does this string/pattern appear across the repo" — a genuinely different, complementary query shape needed by agents doing pattern-based investigation (e.g., "find all usages of this deprecated config key"). Zoekt's O(1)-query pre-built index is what keeps this fast regardless of repo size, which matters directly for the Phase 11 scale story even though this section only proves it at MVP scale.

## Expected Architecture

`packages/repo_intel/indexers/zoekt_client.py` shells out to (or calls via HTTP, depending on deployment mode) a Zoekt indexer/search process, building an index from the same repo root as Section 01's Tree-sitter pass. Exposed via `search_codebase(query, top_k) -> list[SearchHit]`, feeding into the hybrid retrieval fusion built in Section 06.

## Dependencies

Phase 00 (sandbox — Zoekt's indexer process should run under the same resource-bounded execution discipline as any other repo-touching subprocess).

## Atomic Implementation Tasks

1. Stand up Zoekt locally (via its indexer binary `zoekt-index` and search server `zoekt-webserver`, or an equivalent packaged deployment) against the fixture/demo repo.
2. Implement `ZoektClient.build_index(root_path)` wrapping the indexer invocation.
3. Implement `ZoektClient.search(query, top_k) -> list[SearchHit]` wrapping the search query API/CLI, normalizing results to a `SearchHit` model (`file_path, line, snippet, score`).
4. Decide and document the Zoekt process lifecycle (long-running local service for dev vs. containerized service) — this decision is revisited in Phase 11 when it becomes a properly operated service; document expectations now, don't over-engineer deployment yet.
5. Integration test: index the fixture repo, run a known-answer search query, assert the expected file/line appears in top results.

## Manual Testing Procedure

1. Build the Zoekt index for the fixture repo.
2. Run 3–5 manual searches for known strings/patterns and confirm expected files rank highly.
3. Modify a file, rebuild the index, confirm the change is reflected (full rebuild is fine here — incremental Zoekt updates are addressed in Section 05).

## Expected Demo

Terminal output of a Zoekt search query against the fixture repo showing ranked results with file/line/snippet — a second, independent retrieval modality proven working alongside Section 01's symbol lookups.

## Acceptance Criteria

- [ ] Zoekt index builds successfully against the fixture/demo repo.
- [ ] Known-answer search queries return the expected file(s) in the top-K results.
- [ ] `ZoektClient.search` results are normalized into a stable `SearchHit` schema consumable by later hybrid fusion (Section 06).

## Risks

- **Risk:** Operating Zoekt as a separate process/service is new operational surface for a solo engineer. **Mitigation:** keep it as simple as possible at MVP (local process, documented start/stop in the `Makefile`) — don't containerize/orchestrate it prematurely; that's appropriate scaling work for Phase 11 when it's genuinely a shared service under real concurrent load.

## Future Improvements

- Federated per-shard Zoekt indexes — Phase 11.

## Research Opportunities

None — Zoekt's behavior is well-documented externally; this section is integration work, not open design.
