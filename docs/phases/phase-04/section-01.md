# Section 01 — Question Bank & Data Model

## Objective

Implement the `Question` dataclass (§E.4) and populate an initial question bank organized by category (business objective, functional, non-functional, security/compliance, performance, scalability, reliability, data integrity, API contracts, deployment constraints), stored as versioned config per §Q's `configs/question_bank/`.

## Why It Exists

A hardcoded, in-code question list would violate the "policy configs go through PR review, versioned" principle (§N) that this whole system applies to workflow rules and pricing — questions are exactly this kind of tunable policy. Building the bank as config-driven from day one means later tuning (Phase 15's evaluation might reveal certain questions are low-value) is a config change, not a code change.

## Expected Architecture

`packages/requirements_engine/models.py` defines `Question` exactly per §E.4 (`id, text, category, applies_if, auto_answerable_from, depends_on`). `applies_if` is a `Callable[[WorkflowContext], bool]` — since `WorkflowContext` itself is formally defined in Phase 10 (§F.2), this section defines a minimal working subset of `WorkflowContext` locally (work_type, risk_tier, touches auth/PII flags, repo_architecture, has_database_changes, etc. — the fields §E.4's dependency DAG actually reads) and Phase 10 later reconciles it into the full schema. The question bank itself lives in `configs/question_bank/*.yaml`, loaded and validated into `Question` objects at startup.

## Dependencies

None beyond Phase 00 (config loading pattern).

## Atomic Implementation Tasks

1. Implement the `Question` dataclass/Pydantic model per §E.4.
2. Define a minimal `WorkflowContext`-subset type sufficient for `applies_if` predicates at this phase — document explicitly that Phase 10 will supersede/merge this with the full §F.2 schema, and that this is a deliberate, temporary simplification, not a design mistake.
3. Author the initial question bank in YAML covering every category named in §E.4, seeded directly from the partial dependency DAG shown in §E.4 (Q1–Q8h, Qsec1–3, Qint1–3, Qdb1–3) plus reasonable additions per category not explicitly enumerated in the blueprint (the blueprint's DAG is explicitly "(Partial)").
4. Implement a loader (`load_question_bank(path) -> list[Question]`) that parses YAML into validated `Question` objects, failing loudly (not silently skipping) on a malformed entry.
5. Unit tests: every question in the bank parses successfully; `depends_on` references only IDs that exist in the bank (referential integrity check — catches typos before they cause silent DAG bugs in Section 02).

## Manual Testing Procedure

1. Load the question bank and print the full list grouped by category.
2. Deliberately introduce a typo in a `depends_on` reference and confirm the loader's validation catches it.
3. Review the bank's category coverage against §E.4's list by eye — confirm every named category has at least a few questions.

## Expected Demo

Terminal output listing the full question bank grouped by category, with a summary count per category — proving the bank exists, is complete, and is validated.

## Acceptance Criteria

- [ ] Every category named in §E.4 has at least one question.
- [ ] `depends_on` referential integrity is validated at load time and covered by a test that catches a broken reference.
- [ ] The question bank is stored as reviewable config (YAML), not hardcoded Python.

## Risks

- **Risk:** An under-populated question bank produces shallow requirements gathering that later phases (Design, Implementation) inherit as ambiguity. **Mitigation:** treat the bank as a living artifact — Phase 15's evaluation (ambiguity rate KPI, ambiguity rate < 10% target per §L.2) is the long-term feedback signal for whether it needs expansion; don't try to make it exhaustive up front.

## Future Improvements

- Expand the bank based on real usage patterns once Phase 05+ generates real requirements sessions.

## Research Opportunities

Which question categories correlate most strongly with downstream rework (Design rework rate, §L.2) is a genuinely interesting empirical question — but only answerable once Phase 15's evaluation pipeline and enough task volume exist. Note it here as a hypothesis to test later.
