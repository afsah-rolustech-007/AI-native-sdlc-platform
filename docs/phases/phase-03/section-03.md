# Section 03 — NetworkX Dependency Graph (L2, MVP)

## Objective

Build the dependency/call graph layer (§G.2 L2) using NetworkX, in-process, as the MVP graph backend per the blueprint's explicit MVP→scale path (NetworkX now, Neo4j at Phase 11) — exposing `get_callers`, `get_callees`, `get_dependencies`, `get_dependents`, `get_impact_set`.

## Why It Exists

This is what makes impact-aware retrieval possible — Phase 06's Implementation Manager and Phase 07's Dependency Impact Agent both fundamentally depend on graph traversal, not just symbol lookup or text search. Building it as an in-process NetworkX graph now (zero infra cost) while designing the `RepositoryIntelligence` interface to hide the backend (per §G.1) is what makes the Phase 11 Neo4j migration a backend swap, not a rewrite.

## Expected Architecture

`packages/repo_intel/graph/networkx_client.py` builds a `networkx.DiGraph` where nodes are symbols/files (from Section 01's Tree-sitter output) and edges represent import/call relationships, derived from Tree-sitter's reference resolution. `packages/repo_intel/graph/bfs.py` implements bounded-depth BFS traversal for `get_callers`/`get_callees`/`get_impact_set`. The graph is rebuilt (or incrementally updated, Section 05) alongside the symbol index — same trigger, same incremental scope, per §G.2's stated update pattern.

## Dependencies

Section 01 (symbols and their reference relationships are the graph's nodes/edges).

## Atomic Implementation Tasks

1. Implement edge extraction from Tree-sitter output: import statements → file-level edges; function calls → symbol-level edges (best-effort static resolution — document known limitations, e.g., dynamic dispatch, as an explicit non-goal at MVP).
2. Build the `networkx.DiGraph` construction pipeline from extracted edges.
3. Implement `get_callers(symbol_id, depth) -> list[Symbol]` and `get_callees(symbol_id, depth) -> list[Symbol]` as bounded-depth graph traversals.
4. Implement `get_dependencies(file_path) -> list[str]` and `get_dependents(file_path) -> list[str]` at file granularity.
5. Implement `get_impact_set(changed_files) -> ImpactSet` — BFS outward from changed files to their dependents, bounded by a configurable depth (this is what Phase 07's test-impact analysis will call directly).
6. Unit tests against the fixture repo: known caller/callee relationships resolve correctly; `get_impact_set` for a leaf-module change correctly excludes unrelated modules and includes known dependents.

## Manual Testing Procedure

1. Build the graph for the fixture repo.
2. Query `get_callers`/`get_callees` for a function with known, hand-verified relationships.
3. Simulate a change to one file and call `get_impact_set`, manually verifying the returned set against your own understanding of the fixture repo's structure.

## Expected Demo

A small visualization (even a printed adjacency list, or a `networkx`-generated graph image for the fixture repo) alongside terminal output of `get_impact_set` for a simulated change, showing the correctly bounded set of affected files.

## Acceptance Criteria

- [ ] Graph correctly represents known import/call relationships in the fixture repo (verified by hand against a small, fully-understood fixture).
- [ ] `get_callers`/`get_callees` respect the requested depth parameter.
- [ ] `get_impact_set` produces a correct, bounded set of affected files for a simulated change — this directly de-risks Phase 07's test-impact analysis.

## Risks

- **Risk:** Static call-graph resolution is inherently incomplete for dynamic languages (reflection, dynamic imports, duck typing). **Mitigation:** document this as a known precision ceiling, not a bug to chase indefinitely; the confidence model (§B.4) and QA's test-impact analysis (§K.2) are designed to tolerate imperfect retrieval, not require perfect static analysis.

## Future Improvements

- Neo4j migration for multi-hop Cypher queries at scale — Phase 11.
- Cross-shard dependency edges — Phase 11 (§G.4).

## Research Opportunities

Measure how much static-resolution imprecision actually affects downstream QA/impact-analysis accuracy once Phase 07 exists — this quantifies whether deeper resolution (e.g., type-informed analysis) is worth the investment later.
