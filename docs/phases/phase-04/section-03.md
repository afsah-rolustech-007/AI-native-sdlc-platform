# Section 03 — Auto-Answer-from-Repo Integration

## Objective

Before any question reaches a human, check whether Repository Intelligence (Phase 03) can answer it with high confidence — tech stack, existing API contracts, current test coverage, existing patterns — and surface auto-answered questions transparently (not hidden) per §E.4.

## Why It Exists

This is the engine's core differentiator over a static intake form: it does real retrieval work before bothering a human, and shows its work. This is also the first place in the roadmap where Phase 03's Repository Intelligence and Phase 04's engine actually meet — proving the dependency drawn in `architecture.md` is real, not just diagrammed.

## Expected Architecture

Each `Question` with `auto_answerable_from == "repo_intelligence"` gets routed, before being queued for a human, through a `RepoAnswerResolver` that maps the question's category/intent to specific `RepositoryIntelligence` calls (e.g., "what's the current tech stack" → `get_architecture_summary()`; "does an API contract already exist for this resource" → `search_concepts`/`get_file_structure` against the relevant module). The resolver returns either a confident answer (with the retrieved evidence attached) or `None` (defer to human). Auto-answered questions are recorded in the session trace with their evidence, not silently dropped.

## Dependencies

Phase 03 (`RepositoryIntelligence`), Section 02 (question queue to intercept before human-facing).

## Atomic Implementation Tasks

1. Define the mapping from auto-answerable question categories/IDs to specific `RepositoryIntelligence` method calls — this mapping is itself config-like and should live alongside the question bank (Section 01), not buried in code, since it will need tuning.
2. Implement `RepoAnswerResolver.try_answer(question, repo_intel) -> AutoAnswer | None`, where `AutoAnswer` carries `{answer_text, evidence_refs, confidence}`.
3. Implement a confidence threshold for accepting an auto-answer vs. deferring to a human (a question with a weak/ambiguous retrieval result should still reach the human, not be force-answered incorrectly) — this is a direct, small-scale application of Fail-Closed (Principle 8): low-confidence auto-answer attempts default to "ask the human," never to "guess."
4. Wire `RepoAnswerResolver` into `QuestionQueue.next()`: before yielding a question to the caller, attempt auto-answer first; if successful, record it and skip to the next question; only yield genuinely human-bound questions.
5. Unit/integration tests against the Phase 03 fixture repo: a tech-stack question is correctly auto-answered from `get_architecture_summary()`; a business-objective question (never auto-answerable) always reaches the human; a borderline retrieval (low confidence) correctly defers to human rather than guessing.

## Manual Testing Procedure

1. Run the well-specified demo scenario (Phase 04 README) against the Phase 03 fixture repo and confirm several questions are auto-answered with correct, repo-grounded evidence shown.
2. Manually inspect the auto-answered evidence for accuracy — this is a case where "the retrieval found *something*" is not sufficient; the *answer* must be correct.
3. Confirm the session trace clearly distinguishes auto-answered questions (with evidence) from human-answered ones — this is what Screen 2 (§P, Phase 09) will render later, so get the data shape right now.

## Expected Demo

CLI output showing a mix of auto-answered questions (with their retrieved evidence printed) interleaved with genuinely human-facing questions — visually proving the "auto-answered, not hidden" principle from §E.4.

## Acceptance Criteria

- [ ] Auto-answerable questions are correctly resolved from Repository Intelligence for the fixture repo, with correct, evidence-backed answers.
- [ ] Low-confidence retrieval defers to the human rather than guessing (Fail-Closed applied at this small scale, tested explicitly).
- [ ] Every auto-answered question retains a visible evidence reference in the session trace — never silently answered with no audit trail.
- [ ] Auto-answer rate on the well-specified demo scenario is high, and near-zero on the vague-request demo scenario (since a from-scratch/ambiguous request has little for the repo to answer) — both behaviors are asserted in tests, not just observed anecdotally.

## Risks

- **Risk:** Overconfident auto-answering could silently lock in a wrong assumption that only surfaces as a Design-phase gap much later (an expensive rollback per §D.3's `FL-03` loop). **Mitigation:** the confidence threshold in task 3 is the primary defense; additionally, ensure the evidence is always retained so a human reviewing Screen 2 later (Phase 09) can catch a wrong auto-answer even after the fact.

## Future Improvements

- Expand auto-answerable question coverage as Repository Intelligence matures (Phase 11/12) — a genuinely growing list.

## Research Opportunities

Track auto-answer accuracy (correct vs. later-corrected) once real usage exists — feeds directly into whether the confidence threshold from task 3 needs tuning (a good candidate for the confidence-model recalibration work in Phase 15).
