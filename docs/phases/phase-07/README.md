# Phase 07 — Core QA Agents

## Goal

Replace Phase 01's stub `qa_node` with a real, risk-scoped QA pipeline: impact-aware test selection, bug reproduction before any fix is attempted, and spec-compliance verification — proving the implementation from Phase 06 actually satisfies what was asked, before it ever reaches a human reviewer.

## Why This Phase Exists

Phase 06 proves the platform can *produce* code. This phase proves it can *know whether that code is right* — without running the entire test suite on every change (infeasible at scale, and unnecessary per §K.2's test-impact analysis). It's sequenced immediately after Implementation because QA has nothing real to evaluate until real diffs exist, and because Bug Validation's reproduce-before-fix protocol (§K.3) fundamentally needs a real Implementation pipeline (Phase 06) to route into once a bug is confirmed reproducible.

## Dependencies

Phase 06 (real diffs to test), Phase 03 (dependency graph for impact analysis).

## High-Level Architecture

```
Merged diff (from Phase 06's fan-in) + risk_tier (still fail-closed-default until Phase 10)
        │
        ▼
  QA Manager ── computes QA plan (minimal set at this phase: static analysis always-on
        │         from Phase 06 §07 is reused; this phase adds test execution + spec QA)
        │
        ├──(work_type == bug/hotfix)──▶ Bug Validation Agent (reproduce BEFORE any fix ran)
        │                                     │
        │                              not reproducible──▶ back to Requirements (re-scope)
        │
        ▼
  Dependency Impact Agent ── BFS via get_impact_set (Phase 03) ── expanded test scope
        │
        ▼
  Unit/Integration Test Agent ── runs impact-scoped tests, extends coverage
        │
        ▼
  Spec QA Agent ── compares diff against RequirementsSpec, detects scope creep
        │
        ▼
  Validator(qa) ── confirms QA plan matched risk-tier requirements
        │
        ▼
  [ApprovalGate(release) — Phase 08]
```

## Expected Live Demo

Run two scenarios: (1) the Phase 06 demo feature, now flowing through real QA — impact-scoped test selection, test execution, and Spec QA confirming the implementation matches requirements. (2) A seeded bug report against the demo repo — show Bug Validation Agent reproducing it first, then (after a fix flows through Phase 06 again) re-validating that the reproduction case now passes, with a regression test artifact produced.

## Deliverables

- `packages/agents/qa/qa_manager.py`, `dependency_impact_agent.py`, `bug_validation_agent.py`, `spec_qa_agent.py`.
- `packages/qa/static_analysis.py` extended with impact-scoped `pytest` execution.
- `Validator`(qa) instance.
- Real `qa` graph node.

## Sections

1. [QA Manager & Risk-Scoped QA Plan](section-01.md)
2. [Dependency Impact Agent & Test-Impact Analysis](section-02.md)
3. [Unit/Integration Test Agent](section-03.md)
4. [Bug Validation Agent & Bug Protocol](section-04.md)
5. [Spec QA Agent & Validator(qa)](section-05.md)
