# Section 02 — resolve_workflow_profile() & the Ordered Rule Table

## Objective

Implement `resolve_workflow_profile()` exactly per §F.3's ordered, first-match-wins rule function, and §F.4's agent-selection rule table, replacing the fail-closed default profile everywhere it's currently hardcoded across Phases 05–09.

## Why It Exists

This is the phase's centerpiece — the function that makes routing "deterministic and auditable over clever and opaque" (Principle 5) a reality rather than a design intention. Every `ApprovalGate`'s `applies_when`, every QA depth setting, every model tier choice from this point forward is driven by this one, unit-tested function.

## Expected Architecture

`packages/workflow_engine/policy.py`'s `resolve_workflow_profile(task, ctx) -> WorkflowProfile` implements §F.3's five ordered rules exactly, starting from `WorkflowProfile.most_conservative()` as the fail-closed base case (meaning: if somehow no rule matches — which shouldn't happen given Rule 5 is a catch-all, but defensively — the conservative default is still the floor, not an unguarded fallthrough). §F.4's agent-selection table is implemented as a second function, `select_active_agents(ctx) -> set[AgentId]`, consumed alongside the profile. Every call site built in Phases 05–09 that currently uses the hardcoded conservative default (`ApprovalGate.applies_when`, QA Manager's depth setting, CodeGen's model tier assignment) is updated to call `resolve_workflow_profile()` instead.

## Dependencies

Section 01 (`WorkflowContext`), every phase 05–09 call site that currently hardcodes the conservative default.

## Atomic Implementation Tasks

1. Implement `resolve_workflow_profile()` per §F.3's exact five rules, in exact order.
2. Implement `select_active_agents()` per §F.4's table (hotfix→Bug Validation+Rollback, skip Design+Security; risk≥High→Security/Performance QA/Exploratory; risk==Low→skip Mutation/Exploratory/Performance; has_database_changes→DB Migration Validator; etc.) — note explicitly which agents this activates are not yet built (Mutation Testing, Exploratory Testing, Performance QA are Phase 13; DB Migration Validator, API Contract Validator are not yet built either) — implement the *selection logic* now, correctly, even though some selected agents are still `NotImplementedError` stubs until later phases build them.
3. Write the explicit "every pair of rules is unit-tested for non-overlap" test suite §F.3 calls for — this is a real, specific testing requirement, not just general coverage: write tests proving Rule 1 and Rule 2 cannot both match ambiguously, etc.
4. Update every Phase 05–09 call site (each `ApprovalGate`'s `applies_when`, QA Manager's depth, CodeGen's tier selection) to consume `resolve_workflow_profile()`'s output instead of the hardcoded conservative default — this is a real, non-trivial integration task touching multiple prior phases' code, not just new code.
5. Build the full risk×work_type×confidence test matrix — the blueprint's explicit Phase 10 completion criterion: "every risk×work_type×confidence combination has a passing test."
6. Validate routing against human-architect judgment: construct or recall ~10-20 representative real/synthetic scenarios, manually determine what a human architect would reasonably decide, run them through `resolve_workflow_profile()`, and measure agreement — targeting the blueprint's explicit ≥90% match criterion.

## Manual Testing Procedure

1. Run the three demo scenarios from the Phase 10 README and confirm each produces the expected, differentiated `WorkflowProfile`.
2. Re-run the Phase 06 demo feature end-to-end now driven by real routing (instead of the conservative default) and confirm behavior changes appropriately (e.g., fewer approval interrupts for a genuinely low-risk, high-confidence case).
3. Review the human-judgment-agreement scenario results and investigate any disagreement.

## Expected Demo

This section's demo *is* Phase 10's overall live demo (see README): the three differentiated routing runs, the full unit test suite passing, and the human-judgment agreement measurement printed.

## Acceptance Criteria

- [ ] `resolve_workflow_profile()` matches §F.3's exact rule order and logic.
- [ ] Every rule pair is proven non-overlapping via explicit tests.
- [ ] Every risk×work_type×confidence combination has a passing test — the blueprint's stated completion criterion.
- [ ] Routing matches human-architect judgment ≥90% on the labeled scenario set — measured, not assumed.
- [ ] Every Phase 05–09 hardcoded-conservative-default call site now consumes real routing output.

## Risks

- **Risk:** Retrofitting real routing into five prior phases' code is the largest integration surface in the roadmap so far — regressions in previously-working behavior are a real risk. **Mitigation:** re-run every prior phase's existing integration tests after this section's changes, treating any behavior change as requiring explicit justification (either "this is the intended effect of real routing" or "this is a regression to fix"), not silently accepted either way.

## Future Improvements

- Recalibrating rule thresholds (e.g., `AUTO_MERGE_CEILING`, `CONFIDENCE_FLOOR`) based on real outcome data — Phase 15.

## Research Opportunities

The human-judgment-agreement measurement (task 6) is itself worth treating as an ongoing, re-run benchmark (not a one-time check) — re-run it whenever rules change, and consider it a leading indicator for Phase 15's more formal golden-dataset evaluation.
