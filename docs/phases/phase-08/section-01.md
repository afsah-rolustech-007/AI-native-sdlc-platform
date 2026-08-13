# Section 01 — ApprovalGate Wiring at All Remaining Checkpoints

## Objective

Instantiate the remaining `ApprovalGate` checkpoints from §E.1's enum (`pr`, `deployment` — `scope` and `design` already exist from Phases 05–06) using the template built in Phase 05 §02, and implement the `hitl_log`/`hitl_queue` persistence that makes every pending and past approval fully queryable — the data backbone Phase 09's UI will render directly.

## Why It Exists

Phase 05 proved the `ApprovalGate` template works for one checkpoint. This section proves it generalizes cleanly to the remaining checkpoints without modification — the actual test of whether §E.1's "two templates, not N bespoke classes" decision held up under a fuller range of use cases (a pre-merge review gate and a mandatory, mission-critical deployment gate are meaningfully different in stakes, even though they're the same class).

## Expected Architecture

`ApprovalGate`(pr) and `ApprovalGate`(deployment) are configured per §E.1/§E.8: `pr` fires for Medium+ risk (fail-closed default: currently fires for all, per `roadmap.md` §2.4); `deployment` **always fires for production regardless of confidence** (§E.8: "Mandatory for every production deploy regardless of confidence (Principle 4)" — this is the one checkpoint that must never become conditional, even after Phase 10's real routing exists). Every `ApprovalGate` invocation writes a row to `hitl_log` (§R) at creation and updates it on response, and every decision writes an `ApprovalRecord` to `approvals` (§R) — this section is what makes those two tables (scaffolded empty since Phase 00 §02) finally load-bearing.

Every `hitl_log` row's `request_type` (§B.2's `HITLRequest` discriminant: `clarification` | `approval` | `policy_review` | `risk_approval`) is set to `"approval"` for all four checkpoints instantiated here — this is what lets Phase 09's Screen 7 (clarification queue) and Screen 8 (approval requests) query the same table with a `WHERE request_type=...` filter instead of relying on an implicit convention. `clarification`-type rows come from Phase 04/05's Requirements Analyst and Section 06's Clarification Escalation path (§D.9.3), not from this section.

## Dependencies

Phase 05 §02 (`ApprovalGate` template), Phase 00 §02 (`hitl_log`/`approvals` tables).

## Atomic Implementation Tasks

1. Configure `ApprovalGate`(pr) with its evidence bundle spec pointing at Section 02's (this phase's) full evidence bundle, not Phase 05's minimal placeholder.
2. Configure `ApprovalGate`(deployment) with the hardcoded-true firing condition — write an explicit test asserting this gate fires even when a hypothetical high-confidence/low-risk task is passed in, to lock in Principle 4 as code, not just convention.
3. Implement `hitl_log` write-on-create and update-on-response for every `ApprovalGate` firing (retrofit this onto Phase 05's `scope`/`design` gates too, since they were built before this persistence layer was formalized).
4. Implement `ApprovalRecord` persistence to `approvals` on every decision.
5. Implement a `list_pending_hitl(user_role)` query function — the first read-path Phase 09's Screen 7/8 will call directly.
6. Integration test: trigger all four `ApprovalGate` checkpoints (`scope`, `design`, `pr`, `deployment`) across a full task run, confirm every one is correctly persisted and queryable, and confirm `deployment`'s unconditional-firing test passes.

## Manual Testing Procedure

1. Run a task end-to-end through all four checkpoints, approving each via the resume script.
2. Query `hitl_log` and `approvals` directly via `psql` after the run and confirm a complete, correct record of every decision.
3. Run the unconditional-firing test for `ApprovalGate`(deployment) and confirm it cannot be bypassed by any current input.

## Expected Demo

A `psql` query output showing the complete `hitl_log`/`approvals` audit trail for one full task run across all four checkpoints — the first time in the roadmap the full HITL history of a task is inspectable in one place.

## Acceptance Criteria

- [ ] All four `ApprovalGate` checkpoints (`scope`, `design`, `pr`, `deployment`) are instantiated from the same unmodified template class.
- [ ] `ApprovalGate`(deployment) is proven, via an explicit test, to fire unconditionally for production deployments regardless of confidence/risk inputs.
- [ ] Every approval decision across all checkpoints is persisted to `hitl_log`/`approvals` and queryable.

## Risks

- **Risk:** A future well-intentioned optimization ("skip approval if X") could accidentally weaken `ApprovalGate`(deployment)'s unconditional guarantee. **Mitigation:** the explicit lock-in test from task 2 is a regression guard specifically against this — treat any change to this test as requiring the same scrutiny as a change to Principle 4 itself.

## Future Improvements

- Evidence bundle richness continues growing through Phase 13 (security/mutation findings) and Phase 14 (real PR provider data).

## Research Opportunities

None — this section is safety-critical plumbing, deliberately conservative.
