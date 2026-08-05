# Section 03 — Validator(design), ApprovalGate(design) & Design Feedback Loops

## Objective

Implement `Validator`(design) (checklist-based: boundaries, contracts, failure handling), `ApprovalGate`(design), and the `FL-02`/`FL-03` feedback loops (§F.5) — closing out the Design phase and activating MASC Check 3 (semantic drift) for the first time, since Design is one of §E.6's `HIGH_STAKES_PHASES`.

## Why It Exists

This is where the platform proves its central safety pattern for the first time at real stakes: an independent validator, separate from the producing agent, gates whether a design is good enough to spend implementation budget on — and a genuinely different failure mode (a design-phase discovery that requirements were actually incomplete) correctly triggers a full-phase rollback with mandatory HITL, per §D.3's rollback table.

## Expected Architecture

`Validator`(design) is a Section 02 (Phase 05)-template instance configured with `rule_set="design-checklist"`, `independent_of=DesignManager` — evaluating `ArchitectureDoc` against a checklist (component boundaries clearly defined? API contracts specified? failure handling addressed? does it cover 100% of requirements per §L.2's Design KPI?). On failure, it distinguishes two failure kinds per §D.3/§F.5: a **design gap** (routes `FL-02` back to Design Manager, same phase, max 5×) vs. a **requirement gap** (routes `FL-03` back to the full Requirements phase, max 1×, mandatory HITL). MASC Check 3 (semantic drift, §E.6) activates here: compares the design against `SDLCState.requirements`/`intent_version` to catch drift from what was actually approved. `ApprovalGate`(design) fires per the still-provisional risk-tier logic (fail-closed default until Phase 10).

## Dependencies

Sections 01–02 (`ArchitectureDoc` to validate), Phase 05 §01 (MASC Check 3 stub to now implement fully).

## Atomic Implementation Tasks

1. Implement MASC Check 3 fully (§E.6): a fast-model call comparing the design's key decisions against `state["requirements"]` and `intent_version`, flagging `semantic_drift` if the design has silently diverged from what was approved.
2. Implement `Validator`(design)'s `design-checklist` rule set, distinguishing design-gap vs. requirement-gap failure classification (this classification itself is a real judgment the validator's prompt must make explicitly, not something inferred after the fact).
3. Implement `FL-02` (design gap → Design Manager, max 5×, same phase) and `FL-03` (requirement gap → Requirements phase, max 1×, mandatory HITL) per the Feedback Loop Registry shape (§F.5) — even though the full registry (with all 11 loops centrally tracked) isn't formalized until Phase 10, implement these two loops' actual routing logic now, correctly.
4. Implement `ApprovalGate`(design) using Phase 05 §02's template.
5. Implement the `rollback_count` increment on every loop firing, and wire a basic version of the global guard (`rollback_count >= max_retries_per_node × active_phases → suspend`, §F.5) even though its full context (all phases' loops) doesn't exist until later — a partial-but-correct implementation is appropriate here, extended incrementally.
6. Integration tests: a deliberately incomplete design (missing a requirement's coverage) triggers `Validator`(design) failure classified as a design gap, routes `FL-02`, and a corrected resubmission passes; a design that reveals an actual requirements ambiguity triggers `FL-03` with a real `interrupt()` for HITL; a design deliberately diverging from approved requirements is caught by MASC Check 3.

## Manual Testing Procedure

1. Run the demo feature through Design with a deliberately weakened first-pass design (e.g., temporarily disable the reflection pass from Section 02 for one test run) and confirm `Validator`(design) catches the gap and `FL-02` fires.
2. Force a requirement-gap scenario (a design decision that reveals the requirements didn't specify something needed) and confirm `FL-03` fires with a real HITL interrupt, and that a human response correctly resumes the flow back through requirements.
3. Confirm `ApprovalGate`(design) pauses and correctly processes an approval.

## Expected Demo

Terminal walkthrough of all three paths: a caught design gap correctly looping back and resolving; a requirement gap correctly escalating to HITL; a clean design passing through directly to `ApprovalGate`(design) and being approved.

## Acceptance Criteria

- [ ] `Validator`(design) correctly distinguishes design-gap vs. requirement-gap failures and routes `FL-02`/`FL-03` accordingly.
- [ ] MASC Check 3 (semantic drift) is fully active for the design phase and demonstrably catches a deliberately induced drift case.
- [ ] `FL-02`'s 5× cap and `FL-03`'s 1×-with-mandatory-HITL cap are enforced, not just documented.
- [ ] `ApprovalGate`(design) functions correctly end-to-end.

## Risks

- **Risk:** A validator prompt that's too lenient defeats the entire safety purpose of this section; too strict creates unproductive feedback loops that never converge. **Mitigation:** track (informally now, formally once Phase 15 exists) the loop resolution rate for `FL-02`/`FL-03` — a validator that never fails, or one whose failures never resolve within the cap, are both signals worth investigating rather than ignoring.

## Future Improvements

- Full centralized Feedback Loop Registry with all 11 named loops — Phase 10.
- Validator-of-Validator pattern (§E.3) for this specific high-stakes checkpoint — worth considering once real failure data suggests the design validator itself is occasionally wrong.

## Research Opportunities

This is the first place in the roadmap where "does an independent validator actually catch what it's supposed to" becomes empirically testable — worth deliberately seeding a few known-bad designs through this pipeline as an informal benchmark, ahead of Phase 15's formal golden dataset.
