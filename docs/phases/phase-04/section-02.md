# Section 02 — Question Dependency DAG & Predicate Engine

## Objective

Implement the traversal engine that walks the question bank as a dependency DAG (§E.4's example: Q1 → Qsec1 → Qsec2 → Qsec3 if touches auth/payments/PII; Q3 branching by work_type; conditional sub-DAGs for microservices/database changes), respecting `applies_if` predicates and `depends_on` ordering, and producing an ordered queue of questions to ask.

## Why It Exists

A flat checklist asks irrelevant questions (performance targets for a one-line typo fix) and misses conditionally-required ones (compliance questions only surface when the request actually touches PII). The DAG is what makes this "dynamic" rather than "a form" — directly serving Principle 3 (structured clarification over silent assumption) without over-asking.

## Expected Architecture

`packages/requirements_engine/engine.py`'s `QuestionQueue` class takes the full question bank and a `WorkflowContext`-subset (from Section 01), evaluates `applies_if` for every question, filters to applicable ones, topologically sorts by `depends_on`, and yields questions one at a time — re-evaluating applicability after each answer, since an answer can change context (e.g., answering "yes" to `has_database_changes` newly activates the `Qdb*` sub-DAG).

## Dependencies

Section 01 (question bank and its predicate/dependency fields).

## Atomic Implementation Tasks

1. Implement `applies_if` evaluation against the current `WorkflowContext`-subset state, re-evaluated after every answer (not computed once at the start) — this is what makes conditional sub-DAG activation (e.g., `Qdb1-3` after "has_database_changes" is answered) work correctly.
2. Implement topological ordering respecting `depends_on`, with cycle detection (fail loudly — a cyclic dependency in the bank is a config bug, not a runtime condition to route around).
3. Implement `QuestionQueue.next() -> Question | None` — returns the next applicable, dependency-satisfied, unanswered question, or `None` when the queue is exhausted.
4. Implement `QuestionQueue.answer(question_id, answer)` — records the answer, updates the context state, triggers re-evaluation of applicability for not-yet-asked questions.
5. Unit tests replicating §E.4's example DAG exactly: touching auth triggers the `Qsec*` chain; `work_type=bug` triggers `Q4b/Q5b/Q6b` instead of `Q4/Q5/Q6`; answering "has_database_changes=true" activates `Qdb1-3` mid-session (not just at session start).

## Manual Testing Procedure

1. Run the three demo scenarios from the Phase 04 README (well-specified feature, vague request, security-sensitive request) through `QuestionQueue` interactively via CLI, answering prompts.
2. Confirm the security-sensitive scenario surfaces exactly the `Qsec1-3` chain and not, e.g., the `Qint*` microservices chain (unless also applicable).
3. Confirm mid-session context changes (answering a question that flips a flag) correctly activate previously-inapplicable questions.

## Expected Demo

An interactive CLI session showing the question queue adapting live — asking a question, receiving an answer that changes context, and the next question being one that wasn't applicable before that answer.

## Acceptance Criteria

- [ ] The engine reproduces §E.4's example DAG behavior exactly for the documented scenarios (auth/PII → compliance chain; work_type branching; microservices/database conditional chains).
- [ ] Applicability is re-evaluated after every answer, not fixed at session start.
- [ ] Cyclic dependencies in the bank are detected and rejected at load time, not discovered as an infinite loop at runtime.

## Risks

- **Risk:** A predicate referencing a `WorkflowContext` field that isn't yet set (because the question that would set it hasn't been asked) could silently evaluate to a default/falsy value and skip a needed question. **Mitigation:** unit tests specifically probing this ordering edge case; predicates should be written defensively (explicit "unknown" handling where relevant) rather than assuming a field is always populated by the time it's checked.

## Future Improvements

- Reconcile the local `WorkflowContext`-subset (Section 01) with the full §F.2 schema once Phase 10 builds it.

## Research Opportunities

None — this is deterministic graph traversal, appropriately so per Principle 5.
