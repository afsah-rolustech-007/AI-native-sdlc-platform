# Section 05 — Spec QA Agent & Validator(qa)

## Objective

Implement the Spec QA Agent (§E.8: verifies implementation matches requirements, detects scope creep — always runs) and `Validator`(qa) (confirms the QA plan matched risk-tier requirements), closing out Phase 07's core QA roster.

## Why It Exists

Every other QA check in this phase asks "does the code work" (tests pass, dependencies resolve). Spec QA asks a categorically different question: "does the code do what was actually asked, and nothing more" — directly guarding against silent scope creep, which is a real risk once CodeGen agents (Phase 06) have latitude in how they implement a design. `Validator`(qa) is the meta-check ensuring the QA Manager (Section 01) didn't skip something it should have run.

## Expected Architecture

`packages/agents/qa/spec_qa_agent.py`'s `SpecQAAgent(BaseAgent)` (High-capability tier, §E.8) performs a structured comparison between the final diff and `SDLCState.requirements`' `functional`/`acceptance_criteria` fields, producing a compliance report (`requirement_id → satisfied/not_satisfied/partially_satisfied` plus a `scope_creep_findings` list for changes not traceable to any requirement). On failure, routes `FL-06` (implementation phase, 3×) for missing coverage, or — per §D.3's "QA reveals design defect" row — `FL-07` (design phase, 1×, HITL) if the gap indicates the *design* itself, not just the implementation, missed something. `Validator`(qa) (Fast tier, §E.8) is a `Validator`-template instance with `rule_set="qa-plan-compliance"` checking that the QA Manager's actual executed plan matches what the (currently fail-closed-default) policy required — on failure, the QA Manager re-runs the missing checks (not a full task-level feedback loop, a narrower "redo the QA plan" loop specific to this validator per §E.8).

## Dependencies

Sections 01–04 (full `QAEvidence` to check plan-compliance against), Phase 05 (`RequirementsSpec` to compare against).

## Atomic Implementation Tasks

1. Implement `SpecQAAgent`'s structured comparison: map each `functional`/`acceptance_criteria` entry to evidence in the diff (via retrieval-grounded checking against the actual changed code, not just re-reading the diff's own summary — reuse Phase 03's `RepositoryIntelligence` to verify referenced symbols actually exist/changed as claimed).
2. Implement scope-creep detection: identify changed files/symbols not traceable to any requirement, and require the human reviewer (later, at `ApprovalGate`(release) or `ApprovalGate`(pr), Phase 08) to see these explicitly rather than have them slip through unremarked.
3. Implement the design-defect-vs-implementation-gap distinction (mirroring Phase 06 §03's design-gap-vs-requirement-gap classification pattern) and wire `FL-06`/`FL-07` accordingly.
4. Implement `Validator`(qa)'s `qa-plan-compliance` rule set and its narrower re-run-missing-checks failure path.
5. Implement `QAEvidence.recommendation` (`pass | pass_with_warnings | fail`, §B.2) as the final synthesized output of the whole QA phase, computed from all sections' results plus this section's spec compliance and risk score.
6. Integration test: the demo feature's diff correctly maps to its requirements with no scope creep flagged; a deliberately introduced out-of-scope change (an unrelated file edit) is correctly flagged as scope creep; a deliberately incomplete requirement coverage triggers the correct `FL-06`/`FL-07` classification.

## Manual Testing Procedure

1. Run the demo feature through full QA and inspect the final `QAEvidence.recommendation` and the Spec QA compliance report.
2. Introduce a deliberate, unrelated file change into the diff and confirm it's flagged as scope creep, visible in the evidence bundle.
3. Force a `Validator`(qa) failure (e.g., skip a required check in a test harness) and confirm it correctly triggers a re-run of just the missing check, not the entire QA plan.

## Expected Demo

This section's demo closes out Phase 07's overall live demo (see README): a complete `QAEvidence` bundle for the feature scenario, showing spec compliance, zero scope creep, and a final `pass` recommendation — plus a separate short demo of the scope-creep detection catching a deliberately injected out-of-scope change.

## Acceptance Criteria

- [ ] Spec QA correctly maps requirements to evidence in the diff, grounded in real retrieval (not just re-summarizing the diff).
- [ ] Scope creep is correctly detected for a deliberately introduced out-of-scope change.
- [ ] `Validator`(qa) correctly identifies and triggers re-run of a missing required check.
- [ ] `QAEvidence.recommendation` is correctly computed and reflects the true state of all QA sections combined.

## Risks

- **Risk:** Spec QA's "structured comparison" is itself an LLM judgment call and could pass a subtly incomplete implementation. **Mitigation:** this is precisely why `ApprovalGate`(release) (Phase 08) exists as a human checkpoint downstream — Spec QA reduces the burden on the human reviewer, it does not replace their judgment, especially at Medium+ risk.

## Future Improvements

- Deeper spec-compliance techniques (e.g., property-based verification against acceptance criteria) — Phase 13's property-based testing addition is a related but distinct capability worth connecting once it exists.

## Research Opportunities

Once Phase 15's Fix Rate and Design/QA rework-rate KPIs exist, measure how often Spec QA's `pass` recommendation correlates with an actually-successful human review downstream — a strong signal of whether this agent's judgment is trustworthy enough to eventually support higher autonomy at low risk tiers (Phase 15's shadow-mode graduation concept, §L.3).
