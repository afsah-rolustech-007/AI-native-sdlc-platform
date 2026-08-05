# Phase 05 — Planning & Intake Agents

## Goal

Wire everything built so far — the graph skeleton (Phase 01), model adapters (Phase 02), Repository Intelligence (Phase 03), and the Requirements Engine (Phase 04) — into the platform's first *real* agent phase. By the end of this phase, a real user request produces a real LLM-driven classification, a real requirements-gathering session with real HITL pauses, a real computed confidence score, and a real independent validation — running inside the actual LangGraph graph, checkpointed and resumable.

## Why This Phase Exists

This is the proof point for the entire architecture built in Phases 00–04: do the pieces actually compose? Every subsequent phase (06–09) is "more of the same pattern, applied to more phases" — this is where the pattern itself gets proven once, under real conditions (real interrupts, real model calls, real validation, real budget tracking). Corresponds to `final_plan.md` §E.1 (templates), §E.6 (MASC), §E.7 (Intent Tracker), and the "Phase: Intake & Planning" row of §E.8's agent roster.

## Dependencies

Phase 01 (graph + interrupt/resume), Phase 02 (model calls), Phase 04 (Requirements Engine).

## High-Level Architecture

```
Real intake_node (replaces Phase 01's stub)
   │
   ▼
Planning Manager (classifies Task: work_type, risk_tier — real LLM call)
   │
   ▼
Requirements Analyst (drives Phase 04's QuestioningEngine inside the graph,
   │                   using real interrupt() calls for human-facing questions)
   │
   ▼
Confidence Scorer (calls packages/common/confidence.py with real signals)
   │
   ▼
Validator(requirements)  ── independent consistency check, MASC-validated
   │
   ▼
ApprovalGate(scope)  ── real interrupt(), fires when risk >= Medium
   │
   ▼
[Design phase — still a stub until Phase 06]

Cross-cutting:
- Every agent node wrapped by MASC post-node validation (schema + confidence checks;
  semantic drift check activates in Phase 06 for higher-stakes phases)
- Intent Tracker runs on every new user message, including HITL responses
```

## Expected Live Demo

Submit a real (text) task request through a CLI or minimal API endpoint. Watch it flow through Planning Manager's classification, into a live requirements-gathering session (mixing auto-answered and human-prompted questions via real `interrupt()`/resume calls), through the Confidence Scorer and `Validator`(requirements), and pause at `ApprovalGate`(scope) for a real human decision. Approve it. Confirm the task reaches `TaskState.DESIGN` (even though Design itself is still a stub) with a fully populated `RequirementsSpec`, a logged confidence score, and a complete OTel/cost trail.

## Deliverables

- `packages/agents/base.py` — `BaseAgent` (MASC integration, OTel, retry policy).
- `packages/agents/templates/approval_gate.py`, `validator.py` — the two reusable templates.
- `packages/orchestration/masc.py` — MASC engine (schema + confidence checks active; semantic drift stubbed).
- `packages/orchestration/intent_tracker.py` — Intent Tracker.
- `packages/agents/intake/planning_manager.py`, `packages/agents/requirements/requirements_analyst.py`, `confidence_scorer.py`.
- Real `intake` and `requirements` graph nodes replacing Phase 01's stubs.

## Sections

1. [Agent Base Class & MASC Middleware](section-01.md)
2. [ApprovalGate & Validator Templates](section-02.md)
3. [Planning Manager & Intake Classification](section-03.md)
4. [Requirements Analyst: Wiring the Questioning Engine into the Graph](section-04.md)
5. [Confidence Scorer & Validator(requirements)](section-05.md)
6. [Intent Tracker](section-06.md)
