# Section 01 — Tree-sitter Symbol Index (L1)

## Objective

Build the AST/symbol parsing layer (§G.2 L1) using Tree-sitter: parse source files into symbol tables (functions, classes, methods, imports) queryable by path and name, forming the foundation every other retrieval layer (search, graph, semantic) builds on.

## Why It Exists

Tree-sitter is the platform's foundation for everything symbol-aware: `get_symbol_signature`, `get_symbol_body`, `get_file_structure` (§G.6) all read from this index, and it's the AST source for the never-LLM-generated architecture summary (§G.7). Getting multi-language parsing and incremental re-parse right here means every later consumer (12+ phases of agents) can trust symbol data without re-deriving it.

## Expected Architecture

`packages/repo_intel/indexers/treesitter.py` wraps `py-tree-sitter` (or `tree-sitter-languages`) to parse files per-language into a normalized `Symbol` model (`{id, kind, name, file_path, start_line, end_line, signature, docstring}`), persisted to Postgres (a `symbols` table — new, not in §R's core list since it's an RI-specific table; document this addition). Parsing is per-file and designed to be called both in bulk (initial index) and per-file (incremental, Section 05).

## Dependencies

Phase 00 (Postgres, sandbox for running parser subprocesses if needed for untrusted repo content — note: parsing is read-only and low-risk, but treat any file content as untrusted per §B.6's prompt-injection principle when it later flows into summaries).

## Atomic Implementation Tasks

1. Add Tree-sitter + language grammar dependencies (start with 1–2 languages relevant to the demo repo — e.g., Python, TypeScript — document that language support is additive, not a fixed list).
2. Define the `Symbol` Pydantic model and its Postgres table/migration.
3. Implement `parse_file(path) -> list[Symbol]` extracting functions/classes/methods with signatures and docstrings via Tree-sitter queries.
4. Implement `index_repo(root_path) -> IndexStats` — walks the repo, calls `parse_file` for every source file, bulk-inserts symbols.
5. Implement `get_file_structure(file_path) -> list[Symbol]` and `get_symbol_signature(symbol_id) -> str` / `get_symbol_body(symbol_id) -> str` against the stored index (early implementations of §G.6 methods).
6. Unit tests: parse a small fixture file per supported language, assert expected symbols are extracted with correct line ranges; test a file with syntax errors doesn't crash the whole indexing run (partial-failure tolerance).

## Manual Testing Procedure

1. Run `index_repo()` against a small fixture repo checked into `tests/fixtures/`.
2. Query `get_file_structure` for a known file and manually verify the returned symbols match the file's actual structure.
3. Query `get_symbol_body` for a known function and confirm the returned text matches exactly.

## Expected Demo

Terminal output listing all symbols extracted from a fixture file, followed by `get_symbol_signature`/`get_symbol_body` calls for one symbol showing progressively more detail — this is the first live proof of the "progressive context loading" concept that Phase 12 formalizes later.

## Acceptance Criteria

- [ ] Symbols are correctly extracted (name, kind, line range, signature, docstring) for at least the demo repo's primary language(s).
- [ ] A file with a syntax error does not abort the whole indexing run — it's logged and skipped.
- [ ] `get_symbol_signature`/`get_symbol_body`/`get_file_structure` return correct results against the fixture repo.

## Risks

- **Risk:** Language coverage gaps in a polyglot repo silently produce an incomplete index (some files simply never parsed). **Mitigation:** `IndexStats` must report per-extension parse success/failure counts so gaps are visible, not silent.

## Future Improvements

- Federated per-shard symbol indexes — Phase 11.
- SCIP-formatted export for compiler-grade resolution if precision demands it later (§G.3's note) — not needed at MVP.

## Research Opportunities

Evaluate which additional languages are worth adding based on the actual composition of whatever repo(s) this platform is validated against — don't guess a language list speculatively.
