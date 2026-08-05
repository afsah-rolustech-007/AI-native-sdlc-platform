# Phase 04 — Dynamic Requirements Engine

## Goal

Build the Dynamic Questioning Engine (§E.4) as a standalone, testable package — question bank, dependency DAG, auto-answer-from-repo, and confidence-gated exit — before it's wired into a real agent graph (that wiring is Phase 05). By the end of this phase, the engine can take a raw request plus a repo, and produce a `RequirementsSpec` plus a log of what was asked, what was auto-answered, and why it stopped.

## Why This Phase Exists

The blueprint calls the requirements phase "the platform's most important phase and historically its most under-specified component." Building the engine as a standalone package (not yet embedded in the LangGraph agent graph) lets it be tested exhaustively — dozens of synthetic scenarios — without the overhead of running a full graph for every test case. It only becomes buildable now because it fundamentally depends on Repository Intelligence (Phase 03) for auto-answer-from-repo, its single most differentiating feature over a static checklist.

## Dependencies

Phase 03 (Repository Intelligence, for auto-answering questions from repo context).

## High-Level Architecture

```
Raw request + WorkflowContext ──▶ QuestioningEngine
                                        │
                    ┌───────────────────┼────────────────────┐
                    ▼                   ▼                    ▼
            Question Bank        Dependency DAG        Auto-Answer Check
            (categorized,        (applies_if predicates, (queries RepositoryIntelligence
             tagged questions)    depends_on ordering)    before asking a human)
                    │                   │                    │
                    └───────────────────┴────────────────────┘
                                        │
                                        ▼
                          Confidence-Gated Exit Evaluator
                          (uses the B.4 composite formula,
                           implemented here as a pure function)
                                        │
                        ┌───────────────┼───────────────┐
                        ▼               ▼               ▼
                 Exit: confidence  Exit: human    Exit: HITL
                 floor met         accepts gaps   (confidence stuck)
```

Nothing here touches LangGraph yet — this is a pure, importable engine with its own CLI/test harness, matching `final_plan.md`'s own architectural signal of promoting this to "a dedicated phase and package" (§0.1).

## Expected Live Demo

Run the engine against three synthetic scenarios via CLI: (1) a well-specified feature request that should skip most questions via auto-answer and exit quickly with high confidence, (2) a vague one-line request that should trigger many clarifying questions across categories, (3) a security-sensitive request (touches auth/PII) that should trigger the compliance sub-DAG (Qsec1–Qsec3). Print the full question/answer/auto-answer trace and final `RequirementsSpec` for each.

## Deliverables

- `packages/requirements_engine/models.py` — `Question`, `RequirementsSpec`-adjacent working types.
- `packages/requirements_engine/question_bank.py` + `configs/question_bank/` — categorized questions with predicates.
- `packages/requirements_engine/engine.py` — DAG traversal, auto-answer integration, exit evaluation.
- `packages/common/confidence.py` — the §B.4 composite confidence formula as a standalone, unit-tested pure function.
- CLI test harness with the three demo scenarios above as fixtures.

## Sections

1. [Question Bank & Data Model](section-01.md)
2. [Question Dependency DAG & Predicate Engine](section-02.md)
3. [Auto-Answer-from-Repo Integration](section-03.md)
4. [Confidence Model & Gated Exit Conditions](section-04.md)
