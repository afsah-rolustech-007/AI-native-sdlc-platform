# Section 05 — Confidence Scorer & Validator(requirements)

## Objective

Implement the Confidence Scorer agent (wiring Phase 04 §04's `compute_confidence()` with *real* signals for the first time) and the first real `Validator` template instance (`phase=requirements`, an independent consistency checker per §E.8), plus `ApprovalGate`(scope), closing out the intake/requirements phase's agent roster.

## Why It Exists

Phase 04 implemented `compute_confidence()` exactly per §B.4 and **does not call it with placeholders** (the requirements loop exits on `RequirementsSufficiency`). This section is the **first honest caller**: `retrieval_coverage` from the session's evidence/auto-answer stats, `validator_agreement` from this section's own `Validator`(requirements). `precedent_strength` still has no episodic memory — **omit/fail-closed, do not invent 0.5**. `static_check_cleanliness` at this phase is a structural completeness check (acceptance criteria present, mandatory slots answered), not lint — lint applies from Phase 06 onward. This is also the first place `ApprovalGate` gates a real, meaningful decision (scope sign-off before design spend, §E.8).

## Expected Architecture

`packages/agents/requirements/confidence_scorer.py`'s `ConfidenceScorer(BaseAgent)` gathers the four signals from real sources and calls `compute_confidence()`. `Validator`(requirements) is configured with `rule_set="consistency-checker"` — a rule set that checks the `RequirementsSpec` for internal contradictions, unaddressed mandatory questions for the task's `work_type`, and vague/unfalsifiable acceptance criteria; per §E.1, it is structurally independent of the Requirements Analyst (separate model call, no shared cached state). `ApprovalGate`(scope) is configured per §E.1/§E.8 using `WorkflowProfile.most_conservative()` (§F.1): **`applies_when` = always true** until Phase 10 — meaning scope approval fires unconditionally at this phase. Document this explicitly in code comments; Phase 10 replaces this with real `resolve_workflow_profile()` output.

## Dependencies

Section 04 (`RequirementsSpec` to score/validate), Phase 04 §04 (confidence formula), Section 02 (templates).

## Atomic Implementation Tasks

1. Implement real `retrieval_coverage` derivation from the Requirements Analyst session's auto-answer statistics (Phase 04 §03).
2. Implement `precedent_strength` **without imputation**: episodic memory does not exist yet (Phase 06+). Either leave the signal missing so `compute_confidence()` fail-closes (task treated below floor — consistent with §B.4) **or** pass it only once a documented, real source exists. Do **not** fabricate a similarity search against an empty store and do **not** pass a silent 0.5.
3. Implement `Validator`(requirements)'s `consistency-checker` rule set as a real LLM-backed check (per §E.8's table, Fast tier) producing pass/fail plus specific gaps, feeding `validator_agreement` back into the Confidence Scorer.
4. Implement `static_check_cleanliness` for the requirements phase as a structural completeness check (e.g., are acceptance criteria present and non-empty, are mandatory questions for this work_type answered) — again, document this as the requirements-phase interpretation of a signal that becomes literally "lint/type/security pass rate" once code exists (Phase 06+).
5. Wire `ConfidenceScorer` to run after `Validator`(requirements) (since it needs `validator_agreement`), write `confidence_score` onto both `Task` and `SDLCState`.
6. Implement `ApprovalGate`(scope) using Section 02's template, with the documented temporary firing condition from the architecture note above.
7. Implement `FL-01` (§F.5): `Validator`(requirements) failure routes back to Requirements Analyst with a structured `FeedbackReport` (§D.8) — the platform's first real feedback loop.
8. Integration test: full intake→requirements→confidence→validation→approval flow for both demo scenarios (well-specified, vague), confirming plausible confidence scores and correct approval-gate firing.

## Manual Testing Procedure

1. Run both demo scenarios end-to-end through the real graph, observing the confidence score computed at exit.
2. Manually approve at `ApprovalGate`(scope) for one scenario and reject-with-feedback for the other; confirm the reject path correctly routes back to the Requirements Analyst with the `FeedbackReport`'s specific gaps, not a bare "try again."
3. Query the `approvals` table (Phase 00 §R) to confirm the `ApprovalRecord` is correctly persisted.

## Expected Demo

This section's demo *is* Phase 05's overall closing demo (see README): a complete intake→requirements→confidence→validate→approve run, ending with `TaskState.DESIGN` and a fully audited trail in Postgres.

## Acceptance Criteria

- [ ] Confidence score is computed from real signals (not all placeholders) for every completed requirements session, and logged.
- [ ] `Validator`(requirements) is structurally independent of the Requirements Analyst and produces specific, actionable gaps on failure — feeding `FL-01`'s real feedback loop.
- [ ] `ApprovalGate`(scope) correctly pauses, and correctly routes both approve and reject-with-feedback decisions.
- [ ] Every classification, question, answer, confidence score, validation result, and approval decision for a full session is queryable from Postgres — the complete audit trail promised by this phase's stated goal.

## Risks

- **Risk:** Until episodic memory exists, a missing `precedent_strength` fail-closes §B.4 and every requirements session looks "below floor" to later routers. **Mitigation:** that is the specified Fail-Closed behavior — do not paper over it with a constant. Phase 06+ supplies the signal; Phase 15 recalibrates weights. Document the gap in the scorer's output.

## Future Improvements

- Real `precedent_strength` from episodic memory similarity search — becomes possible once enough completed tasks exist (Phase 06+ generates them; meaningfully useful by Phase 15).

## Research Opportunities

Once several dozen real sessions exist, compare fail-closed-on-missing `precedent_strength` vs a later real episodic signal — informs whether Phase 15's ablation should prioritize this input.
