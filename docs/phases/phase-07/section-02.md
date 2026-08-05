# Section 02 — Dependency Impact Agent & Test-Impact Analysis

## Objective

Implement the Dependency Impact Agent (§E.8: BFS traversal, expands test scope to affected downstream components) and the test-impact analysis default (§K.2): every task runs only tests touching changed code plus downstream dependents, derived from Phase 03's dependency graph — not the full suite, except for Critical risk tier.

## Why It Exists

Running the full test suite on every task is the "full-suite bottleneck at scale" the blueprint explicitly calls out (§K.2) as something to prevent architecturally, not optimize away later. Building impact-scoped testing now, while the test suite is still small, means the discipline (and the code) is already correct by the time repo/test-suite scale makes it load-bearing.

## Expected Architecture

`packages/agents/qa/dependency_impact_agent.py`'s `DependencyImpactAgent` (no LLM — pure graph traversal, §E.8) calls `RepositoryIntelligence.get_impact_set(changed_files)` (already implemented in Phase 03 §03) and maps the resulting impact set to the corresponding test files (via a naming/location convention, or a test-to-source mapping built alongside Phase 03's symbol index if a convention-based mapping proves insufficient). The expanded scope feeds Section 03's Test Agent.

## Dependencies

Phase 03 (`get_impact_set`), Phase 06 (a diff's changed files).

## Atomic Implementation Tasks

1. Implement `DependencyImpactAgent.compute_scope(diff) -> TestScope` wrapping `get_impact_set`.
2. Implement test-file resolution: map affected source files/modules to their test files — start with a simple, documented convention (e.g., `tests/unit/test_<module>.py` mirroring source structure) and note explicitly that this is a placeholder for a more robust mapping if the demo repo's actual test organization differs.
3. Implement the Critical-risk-tier override: full test suite runs instead of impact-scoped, gated by the same fail-closed-default logic used elsewhere until Phase 10 (i.e., document how this override is currently triggered, likely just "always available as a flag, rarely exercised until real risk tiers exist").
4. Unit tests against the Phase 03 fixture repo: a known change's impact set correctly maps to the expected test files; an unrelated test file is correctly excluded.

## Manual Testing Procedure

1. Run the demo feature's diff through the Dependency Impact Agent and print the resulting `TestScope`.
2. Manually verify the scope against your own knowledge of the fixture/demo repo's dependency structure.
3. Force the Critical-risk override and confirm it produces the full test suite instead.

## Expected Demo

Terminal output comparing the impact-scoped test set (small, targeted) against the full test suite (large) for the same diff — a direct, visible illustration of the efficiency this section buys.

## Acceptance Criteria

- [ ] `get_impact_set`-derived scope correctly identifies affected downstream test files for a real diff.
- [ ] Critical-risk override correctly falls back to the full suite when triggered.
- [ ] The convention-based test-file mapping is documented, including its known limitations.

## Risks

- **Risk:** A convention-based source-to-test mapping may miss tests that don't follow the assumed naming/location convention, silently under-testing a change. **Mitigation:** log the mapping's confidence/coverage (e.g., "N source files had no discoverable test file") so gaps are visible, not silent — directly applying the same "auto-answer transparency" philosophy from Phase 04 §03.

## Future Improvements

- More robust test-to-source mapping (e.g., coverage-data-derived rather than convention-based) — worth revisiting if the convention proves too lossy in practice.

## Research Opportunities

Once Phase 15 exists, measure whether impact-scoped testing's defect-detection rate meaningfully differs from full-suite runs on the same tasks — this is the empirical justification (or correction) for the scoping decision made here.
