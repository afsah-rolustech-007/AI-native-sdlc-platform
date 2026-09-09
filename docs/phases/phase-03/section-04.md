# Section 04 — pgvector Semantic Embeddings (L3)

## Objective

Build the semantic embedding layer (§G.2 L3) using pgvector as the MVP vector store (per §G.3's MVP→Qdrant path), enabling `search_concepts` and `find_similar_implementations` — retrieval by meaning, not just symbol name or lexical pattern.

## Why It Exists

Symbol lookup (Section 01) and lexical search (Section 02) both require knowing roughly what you're looking for by name or pattern. Semantic search is what lets an agent (starting Phase 05) ask "find code that does something like X" without knowing the exact identifier — critical for the Requirements Engine's auto-answer-from-repo (Phase 04) and for design/implementation agents finding precedent.

## Expected Architecture

`packages/repo_intel/vector/pgvector_client.py` chunks source files using Section 01 symbol boundaries (never arbitrary line windows) and computes embeddings via `ModelAdapter.embed()` (Phase 02). Vectors live in `code_embeddings`. Cosine similarity (`<=>`) backs `search_concepts` / `find_similar_implementations`.

**Source of truth:** working-tree file bytes. `content_hash` is SHA-256 of the **embedded chunk text**. Parent file hash lives on `indexed_files`. Section 05 re-embeds a chunk only when that hash changed — never because a dependent file changed, never from a git commit id.

**Chunk contract (MVP):**

| Kind | Embedded text |
|---|---|
| `function`, `method` | signature + docstring + full body |
| `class` | signature + docstring only (no method bodies) |
| `module`, `import` | not embedded |

Line ranges on the row still come from the Tree-sitter symbol (a class row spans the whole class even though its vector is header-only). Nested class/function symbols remain separate chunks.

**Token safety:** a hard character budget (`MAX_CHUNK_CHARS`) is applied **before** `embed()`. Oversized function/method chunks fall back to signature+docstring; if still over budget, the text is truncated. The row records `truncated=True`. The provider is never asked to embed overflow text. This is a robustness cap, not a retrieval-quality optimizer.

**`chunk_tokens`:** `ceil(len(chunk_text) / 4)`, a budget hint for Section 06 — not billed embedding tokens (Phase 02 may report usage `unavailable`).

**Identity:** `(repo_root, symbol_id)` with `symbol_id = {file_path}::{qualified_name}`. No FK to `symbols` / `indexed_files` (Section 05 rewrites those tables; CASCADE would force re-embed of unchanged chunks).

**Updates:**

- `index_working_tree()` — skip chunks whose `content_hash` is unchanged; drop rows for files/symbols that disappeared. `rebuild=True` deletes every row for the repo then re-inserts (destructive).
- `reembed_paths([P, …])` reads **only those paths** via `catalog.read_paths()` (not a full tree walk). Pass old and new paths of a move in **one** call.
- Embed new/changed texts **before** any delete/upsert so an embed failure leaves the previous index intact. DB writes are one transaction (rollback restores prior rows).

**Search:** nearest neighbors, then overlapping-span collapse (same `file_path`, overlapping `[start_line, end_line]`: keep the higher-score hit). Optional filters: `kinds`, `paths` (exact `file_path`), `min_score`. These are plumbing for Section 06 — **not** a ranking policy. Fusion, RRF, and precision measurement belong to Section 06.

Phase 02 note: `embed()` may report `TokenUsage.source="unavailable"`. Indexing still stores vectors; do not invent embedding tokens.

## Dependencies

Section 01 (symbol-bounded chunking, catalog walk), Phase 02 (`embed()`).

## Atomic Implementation Tasks

1. Define `code_embeddings` (`symbol_id`, `file_path`, `kind`, `chunk_text`, `embedding vector(N)`, `content_hash`, `start_line`, `end_line`, `chunk_tokens`, `truncated`) plus `content_hash` from day one.
2. Implement chunking: one chunk per class/function/method; class = header only; function/method = signature+docstring+body; apply `MAX_CHUNK_CHARS`.
3. Embedding pipeline: batch `ModelAdapter.embed()`, store vectors + `content_hash`; bulk/chunked writes; skip unchanged hashes.
4. `search_concepts(query, top_k, *, kinds, paths, min_score)` and `find_similar_implementations` — same cosine path; overlap dedup after retrieval.
5. `read_paths(repo_root, paths)` in the catalog; `reembed_paths` must not walk the whole tree.
6. Tests: fixture ranking sanity (not a precision claim); skip-if-unchanged; targeted read; oversized chunk; overlap dedup; filters; cross-file move; insert failure rolls back.

## Manual Testing Procedure

1. Run the embedding pipeline against the fixture tree.
2. Run `search_concepts("function that validates user input")` and confirm the expected symbol appears in top results.
3. Run `find_similar_implementations` with a lightly edited fixture snippet and confirm the original ranks highly.

## Expected Demo

Terminal output of a natural-language `search_concepts` query against the fixture tree returning the semantically correct symbol, alongside the same query as lexical Zoekt (Section 02) that fails by name alone — motivating Section 06 fusion. Fixture ranking is a smoke test, not an accuracy evaluation.

## Acceptance Criteria

- [ ] Embeddings are stored for every class/function/method chunk in the fixture tree.
- [ ] `search_concepts` returns semantically relevant results for a natural-language query that matches no literal identifier (smoke test).
- [ ] `content_hash` is stored per chunk; a second `index_working_tree()` on an unchanged tree performs zero embed calls.
- [ ] `reembed_paths([P])` reads only `P` from disk.
- [ ] Search results include `kind` and `chunk_tokens`; optional `kinds` / `paths` / `min_score` filters work.
- [ ] Overlapping class/method spans do not both appear in the same top-k.
- [ ] Chunks over the character budget are truncated deterministically (`truncated=True`); overflow text is never sent to `embed()`.

## Risks

- **Risk:** Embedding cost scales with repo size. **Mitigation:** skip-if-unchanged + targeted `read_paths` for Section 05; Phase 11 still must revisit full-repo embedding at 1M files.
- **Risk:** Phase 02 embeddings usage/cost may be `unavailable` on Z.AI. **Mitigation:** still persist vectors; do not block indexing on cost telemetry.
- **Risk:** Header-only class chunks and overlap dedup *change* the candidate set but are **not** proven to raise precision. **Mitigation:** do not tune ranking here; Section 06 owns evaluation against lexical + graph.

## Non-goals (this section)

- LLM-summarized chunks, multiple vectors per symbol, query rewriting/expansion.
- ANN indexes (HNSW/IVFFlat), Qdrant, content-based rename reuse, whitespace-insensitive hashing.
- Hybrid fusion / RRF / learned rerank — Section 06.
- Catalog freshness / `StaleIndexError` on search — Section 05.

## Future Improvements

- Qdrant migration — Phase 11/§G.3.
- Embedding-scope gating at massive scale — Phase 11.
- Sub-symbol splitting for huge functions — only after Section 06 precision data exists.

## Research Opportunities

Compare chunking granularity (header-only class vs full class body; whole-symbol vs sub-symbol split) empirically once Section 06's labeled retrieval benchmark exists. Do not promote a variant into the default path without that measurement.
