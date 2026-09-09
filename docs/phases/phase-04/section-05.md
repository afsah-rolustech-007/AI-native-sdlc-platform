# Section 05 — Classification, Auto-Answer, and Question Ranking

## Objective

Turn snapshot + evidence + claims into epistemic statuses and (where safe) auto-answers; rank the remaining human questions with a **transparent additive heuristic**; render those questions from templates grounded in evidence. No extra LLM call.

## Why It Exists

This is the inversion of literal section-03: we do not ask first. We classify, auto-answer what extractors can support, and ask only high-value residuals. Auto-answers stay **visible** in the trace (§E.4, Screen 2 later).

## Expected Architecture

### Classification (`classify.py`)

Deterministic rules, applied after extract and after every evidence batch / human answer:

1. Explicit request or engineer text → `DECISION` (never overwritten by repository FACT).
2. Deterministic repo evidence (snapshot field, manifest name, symbol found, exact lexical identifier) → `FACT` on **repository claims only**.
3. Semantic hits, graph "maybe related," or extractor below threshold → `INFERENCE`.
4. No evidence, no decision → `UNKNOWN`.
5. Two DECISIONs that cannot both hold → `CONTRADICTION` (must be asked; cannot auto-resolve).

Repository FACT "PostgreSQL configured" + DECISION "use MongoDB" → both retained. Activate `Qdb*` / migration slots. Do **not** auto-answer "database = PostgreSQL" as the requirement.

### Auto-answer (`auto_answer.py`)

`try_answer(slot, claims, snapshot, evidence) -> AutoAnswer | None`.

`AutoAnswer` = `{slot_id, answer, evidence_refs, status: fact|inference, confidence: low|medium|high}`.

Accept auto-answer only when:

- the slot's `evidence_plan.accept_as` allows it, and
- the extractor succeeded, and
- the slot is not a pure business/policy DECISION (objectives, SLA numbers, regulatory scope — `evidence_plan` is null).

Low confidence → `None` (ask the human). Inferences may fill the trace as "suggested from repo" **without** counting as an answered mandatory slot unless a later human confirms. Fail closed: when in doubt, ask.

### Ranking (`rank.py`)

**Do not** use the multiplicative `impact × risk × value × unresolved / cost` formula as the implementation. Unnormalized products are unstable and `asking_cost` in the denominator punishes clear questions.

Use:

- **Mandatory gate:** `mandatory` and applicable and unanswered and not accepted auto-answer → always queued, ordered only by `depends_on`. Cannot be ranked away. `Qsec*` stay in this set.
- **Additive score** for the rest, all inputs in `[0, 1]`:

```text
score = 0.35 * impact + 0.25 * risk + 0.25 * information_value + 0.15 * unresolvedness
```

`unresolvedness` is 1 if UNKNOWN, 0.5 if INFERENCE, 0 if FACT/DECISION. If evidence already suffices, `score = 0` (do not ask).

`asking_cost` is a **gate**, not a divisor: skip/defer a slot that is a multi-part essay question until split, or if the session human-question budget is exhausted.

Ask **one** human question per `step()` so answers can re-activate the DAG. Session cap: start at 12 human questions (config).

Weights are v1, named for recalibration. Not BED-LLM.

### Render (`render.py`)

YAML `text` is the generic prompt. `render` templates interpolate evidence ("Repo already has `auth/service.py` and declared `fastapi`. Confirm whether this change should reuse that module, and which auth mechanism is required."). **No LLM render in v1.** If a template is missing, use `text` plus a bullet list of evidence refs.

## Dependencies

Sections 01–04.

## Atomic Implementation Tasks

1. Classifier rules + unit tests for FACT vs DECISION vs contradiction-vs-migration.
2. Extractors: languages from snapshot; service existence by name; dependency name from manifest; symbol existence; lexical identifier present.
3. Auto-answer threshold + trace visibility (auto vs human).
4. Ranker: mandatory gate, additive score, session cap.
5. Template renderer.
6. Tests: well-specified corpus auto-answers stack/auth-module slots; business-objective slot never auto-answers; JWT-in-repo does not auto-answer "which auth method do you want?" when the user did not decide.

## Manual Testing Procedure

1. Well-specified request on the Phase 03 corpus: inspect which slots auto-answered and the evidence.
2. Same repo, request "use MongoDB instead of the current DB": confirm PostgreSQL remains a FACT, MongoDB a DECISION, and a human question about migration appears.
3. Vague one-liner: count human questions; confirm it is not the full bank.

## Expected Demo

Interleaved trace: `AUTO` lines with evidence, `ASK` lines with rendered engineering questions, classifier statuses beside each claim.

## Acceptance Criteria

- [ ] User DECISION is never overwritten by repository FACT.
- [ ] Auto-answers always carry evidence refs.
- [ ] Low-confidence retrieval defers to human.
- [ ] Mandatory security slots cannot be ranked out.
- [ ] No LLM call in this section.

## Risks

- **Risk:** Over-confident auto-answer (FL-03 later). **Mitigation:** extractors strict; semantic ≠ FACT; visible trace.
- **Risk:** Ranking still over-asks. **Mitigation:** session cap + one question per step; tune YAML weights as config.

## Future Improvements

- Phase 05: template output becomes `interrupt()` payload / Screen 2.
- Phase 15: learn weights from which ranked questions engineers actually answered vs skipped.

## Research Opportunities

Log `(slot_id, score, asked, answered, later_corrected)` as the dataset for a future ranker — do not train one now.
