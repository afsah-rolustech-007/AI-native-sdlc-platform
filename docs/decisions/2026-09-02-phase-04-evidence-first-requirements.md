# Decision: Phase 04 requirements engine is evidence-first, not a question-first interview

**Date:** 2026-09-02  
**Status:** Accepted for Phase 04 v1  
**Affects:** `docs/phases/phase-04/`, `docs/architecture.md` §4.3, Phase 05 wiring notes, `final_plan.md` §E.4 control flow (schemas kept)

## Context

§E.4 and the original Phase 04 sections specify a YAML question bank that, for each applicable question, may query Repository Intelligence and then ask a human. That is a checklist with optional auto-answer. It fights Principle 5 (token cost, unbounded RI), over-asks, and can promote repository facts into user decisions.

Phase 03 already provides `get_architecture_summary` (AST JSON, never LLM), `get_aider_repo_map`, `index_status` (`catalog_hash`), and four unfused retrieval signals. A second LLM repo summary would be redundant and more expensive.

## Decision

Implement an **evidence-first hybrid**:

1. One repo-blind structured LLM extract → `ClaimSet`.
2. One session snapshot from Phase 03 metadata + bounded manifests, cached on `catalog_hash`.
3. Deterministic classification (FACT / INFERENCE / DECISION / UNKNOWN / CONTRADICTION).
4. DAG slots + `EvidencePlan` + budgeted targeted RI (semantic last, never FACT).
5. Heuristic ranking; template questions; 3-way exit via `RequirementsSufficiency`.
6. Exact `compute_confidence()` (§B.4) exists as a platform function and **fail-closes** on missing signals. The Phase 04 loop does **not** feed it placeholders.

Still emit §B.2 `RequirementsSpec`. Still keep the YAML bank, visible auto-answers, and 3-way exit **shape**. LangGraph remains Phase 05.

Explicitly out of v1: LLM-as-judge, BED-LLM, learned retrieval router, RRF / `find_relevant_context`, unrestricted ReAct.

## Consequences

- Cheaper sessions (typically **one** LLM call).
- Snapshot must not treat Phase 03 `tech_stack` as frameworks.
- Phase 05 Confidence Scorer is the first honest caller of `compute_confidence()`.
