# Phase 10 — Workflow Policy Engine

## Goal

Replace the fail-closed conservative default profile — used everywhere from Phase 05 through Phase 09 — with real, tested, ordered routing logic: `resolve_workflow_profile()` (§F.3), `escalate_model_tier()`, the full `WorkflowContext` schema (§F.2), and the complete Feedback Loop Registry (§F.5). By the end of this phase, risk tier, confidence, and work type genuinely determine which agents run, how much QA depth applies, which model tier is used, and which approvals are required.

## Why This Phase Exists

`architecture.md` §4.2 explains why this is deliberately late: `resolve_workflow_profile()` can only be validated against real behavior once real agents exist across enough of the SDLC to observe how risk/confidence/work-type actually correlate with good outcomes (Phases 05–09). Building this earlier would mean guessing at rules with nothing to check them against. This phase is a formalization of what was implicitly "everything conservative" — now made precise, differentiated, and unit-tested per risk×work_type×confidence combination.

## Dependencies

Phases 05–09 (real agent behavior across intake through UI, needed to validate routing rules against actual observed outcomes).

## High-Level Architecture

```
Task + real WorkflowContext (full §F.2 schema, replacing every phase's
                              local/partial subset built along the way)
        │
        ▼
  resolve_workflow_profile(task, ctx)  ── ordered, first-match-wins rules (§F.3)
        │
        ├── Rule 1: Critical risk → max caution
        ├── Rule 2: Production hotfix → fast path, mandatory Bug Validation
        ├── Rule 3: Low/failed confidence → escalate regardless of risk
        ├── Rule 4: Low risk + high confidence → auto-merge eligible
        └── Rule 5: Default → standard Medium-risk path
        │
        ▼
  WorkflowProfile ── consumed by every phase built in 05-09:
        - which agents activate (§F.4's agent selection rules)
        - qa_depth (unlocks Phase 13's risk-gated checks)
        - model_tier (feeds escalate_model_tier())
        - approval_requirements (which ApprovalGates actually fire)
        │
        ▼
  Feedback Loop Registry (§F.5) ── all 11 named loops (FL-01 through FL-11)
        centrally tracked, with the global rollback_count guard fully wired
```

## Expected Live Demo

Run the exact same demo feature from Phase 06 three times with different synthetic risk/confidence inputs: (1) Low risk + high confidence — show it skips most approvals and is auto-merge-eligible (still logged/revertible); (2) Critical risk — show every approval checkpoint firing and QA depth set to exhaustive; (3) low/failed confidence — show escalation to Scope+Design approval regardless of the (otherwise low) risk tier. Then show the full unit test suite proving every risk×work_type×confidence combination has a passing test, and that `escalate_model_tier()` correctly upgrades a repeatedly-rejected node's model tier.

## Deliverables

- `packages/workflow_engine/context.py` — full `WorkflowContext` schema (§F.2).
- `packages/workflow_engine/policy.py` — `resolve_workflow_profile()`, `escalate_model_tier()`.
- Full §F.4 agent-selection rule wiring.
- Centralized Feedback Loop Registry (§F.5) with global `rollback_count` guard.
- Test matrix covering every risk×work_type×confidence combination.

## Sections

1. [WorkflowContext Schema & Computed Fields](section-01.md)
2. [resolve_workflow_profile() & the Ordered Rule Table](section-02.md)
3. [escalate_model_tier() & Model Router Integration](section-03.md)
4. [Centralized Feedback Loop Registry & Global Rollback Guard](section-04.md)
