# Section 04 — pgvector Semantic Embeddings (L3)

## Objective

Build the semantic embedding layer (§G.2 L3) using pgvector as the MVP vector store (per §G.3's MVP→Qdrant path), enabling `search_concepts` and `find_similar_implementations` — retrieval by meaning, not just symbol name or lexical pattern.

## Why It Exists

Symbol lookup (Section 01) and lexical search (Section 02) both require knowing roughly what you're looking for by name or pattern. Semantic search is what lets an agent (starting Phase 05) ask "find code that does something like X" without knowing the exact identifier — critical for the Requirements Engine's auto-answer-from-repo (Phase 04) and for design/implementation agents finding precedent.

## Expected Architecture

`packages/repo_intel/vector/pgvector_client.py` chunks source files (function/class-bounded chunks, reusing Section 01's symbol boundaries — do not chunk arbitrarily by line count) and computes embeddings via `ModelAdapter.embed()` (Phase 02), storing vectors in a pgvector-enabled table (`code_embeddings`) alongside file/symbol references. Cosine similarity search backs `search_concepts`/`find_similar_implementations`.

## Dependencies

Section 01 (symbol-bounded chunking), Phase 02 (`embed()` method).

## Atomic Implementation Tasks

1. Define the `code_embeddings` table/migration (`symbol_id`, `file_path`, `chunk_text`, `embedding vector(N)`, `content_hash`) — `content_hash` exists from day one to support the staleness-detection pattern used later (§G.5).
2. Implement chunking: one chunk per symbol (function/class/method) from Section 01's index, using the signature+docstring+body as the embedded text (full body at MVP; compression/skeletal-vs-full distinction is Phase 12's concern).
3. Implement the embedding pipeline: batch-call `ModelAdapter.embed()`, store vectors with `content_hash` for later change detection.
4. Implement `search_concepts(query, top_k) -> list[CodeChunk]` — embed the query, cosine-similarity search via pgvector's `<=>` operator.
5. Implement `find_similar_implementations(code, top_k) -> list[CodeChunk]` — same mechanism, code snippet as query instead of natural language.
6. Unit/integration tests: known-similar code snippets rank near each other; a semantically unrelated query returns low-similarity results (sanity check against a fixture repo with clearly distinct modules).

## Manual Testing Procedure

1. Run the embedding pipeline against the fixture repo.
2. Run `search_concepts("function that validates user input")` (or an equivalent natural-language query matched to a known fixture function) and confirm the expected symbol appears in top results.
3. Run `find_similar_implementations` with a snippet copy-pasted (with minor edits) from the fixture repo and confirm the original ranks highly.

## Expected Demo

Terminal output of a natural-language `search_concepts` query against the fixture repo returning the semantically correct symbol, alongside the same query run as a lexical Zoekt search (Section 02) that fails to find it by name alone — illustrating why both retrieval modes are needed (motivating Section 06's fusion).

## Acceptance Criteria

- [ ] Embeddings are computed and stored for every symbol-bounded chunk in the fixture repo.
- [ ] `search_concepts` returns semantically relevant results for natural-language queries not matching any literal identifier.
- [ ] `content_hash` is stored per chunk, ready for staleness detection in Section 05/§G.5, even though invalidation logic itself is implemented there.

## Risks

- **Risk:** Embedding cost scales with repo size — at MVP scale this is negligible, but the pattern established here (embed everything, always) does not survive to Phase 11 unchanged. **Mitigation:** explicitly flag in Future Improvements that Phase 11 must revisit whether full-repo embedding is still viable at 1M files, or whether embedding scope needs to be relevance-gated.

## Future Improvements

- Qdrant migration for horizontal scaling — Phase 11/§G.3.
- Embedding-scope gating at massive scale (don't embed everything eagerly) — a genuine open question for Phase 11, noted here rather than solved prematurely.

## Research Opportunities

Compare chunking granularity (whole-symbol vs. sub-symbol splitting for very large functions) empirically once real retrieval-precision data exists from Section 06's benchmark.
