# Section 02 — Question Bank, DAG, and Predicate Engine

## Objective

Keep §E.4's question bank as **versioned policy** (YAML, PR-reviewed) and the dependency DAG as the activation mechanism — but treat entries as **requirement slots**, not an interview script. Implement `applies_if` evaluation, `depends_on` topological order, cycle detection, and re-evaluation after every answer.

## Why It Exists

A hardcoded Python list would violate §N (policy through PR). A flat checklist asks irrelevant NFRs and misses conditional compliance questions. The DAG is what makes this dynamic (Principle 3) without becoming a ReAct interviewer (Principle 5).

Literal section-02 yielded `QuestionQueue.next()` as "the next thing to ask a human." That is the question-first loop. This section still yields an **ordered set of activated slots**. Whether a slot becomes an auto-answer or a human question is Section 05.

## Expected Architecture

`configs/question_bank/*.yaml` loaded by `question_bank.py` into `Question` models.

Keep §E.4 fields, and add what evidence-first needs:

```text
id, category, text, applies_if, depends_on
mandatory: bool
evidence_plan: object | null    # Section 04; null = never auto-answer
impact, risk, information_value # 0–1 defaults by category if omitted
render: template string         # Section 05; placeholders for evidence
```

Drop `auto_answerable_from: "repo_intelligence"` as a magic string. Presence and content of `evidence_plan` replace it.

`context.py` defines a **Phase-04 `WorkflowContext` subset** (`work_type`, `risk_tier`, `touches_auth` / `pii` / `payments`, `has_database_changes`, `repo_architecture`, `affected_modules`). Every flag is `T | None` with `None` = unknown. Phase 10 supersedes this with §F.2 — document that explicitly.

Predicate rules:

- Security/compliance slots: if the flag is `None` **or** claims/snapshot suggest auth/PII, **activate** (fail-closed). Do not skip `Qsec*` because the flag was never set.
- Optional NFR slots (`Q4–Q6`): only when `work_type` is `feature` or `new_project`. If `work_type` is unknown, depend on the slot that establishes it — do not ask performance targets for a possible typo fix.
- `has_database_changes` / microservices sub-DAGs: re-evaluate after every answer (literal §E.4 behavior, kept).

`dag.py`: filter applicable → topological sort → cycle detection at **load** time (config bug, not a runtime loop). `QuestionQueue` exposes activated unanswered slots; it does not call RI.

Seed the bank from §E.4's partial DAG (`Q1–Q8h`, `Qsec1–3`, `Qint1–3`, `Qdb1–3`) plus at least one slot per named category.

## Dependencies

Section 01 (`ClaimSet` may set context flags). Phase 00 config-loading pattern.

## Atomic Implementation Tasks

1. `Question` model + YAML schema including `mandatory` and optional `evidence_plan`.
2. `load_question_bank(path)` — fail loudly on malformed entries and on `depends_on` references that do not exist.
3. Cycle detection at load.
4. `WorkflowContext` subset with explicit `None`.
5. `QuestionQueue`: `activated()`, `answer(id, payload)` updates context and re-evaluates.
6. Unit tests: auth → `Qsec*`; `work_type=bug` → `Q4b/Q5b/Q6b` not `Q4/Q5/Q6`; answering `has_database_changes=true` activates `Qdb*` mid-session; unknown `touches_auth` still activates `Qsec*` when claims mention authentication.

## Manual Testing Procedure

1. Print the bank grouped by category with counts.
2. Break a `depends_on` id and confirm the loader rejects it.
3. Drive the three README scenarios through the queue **without** RI — observe which slots activate, not which questions are "asked."

## Expected Demo

Category listing plus a live queue: answering `has_database_changes=true` prints newly activated `Qdb*` ids.

## Acceptance Criteria

- [ ] Every §E.4 category has ≥1 slot. Bank is YAML, not hardcoded Python.
- [ ] `depends_on` integrity and cycles are tested.
- [ ] Applicability re-evaluates after every answer.
- [ ] Security slots fail closed on unknown.

## Risks

- **Risk:** Predicates treat `None` as `False` and skip needed compliance questions. **Mitigation:** unknown-handling tests; security categories treat unknown as activate.

## Future Improvements

- Merge this `WorkflowContext` into Phase 10 §F.2.
- Phase 15: drop low-value slots from the bank using production traces.

## Research Opportunities

Which categories correlate with Design rework (§L.2) — after Phase 15 has volume.
