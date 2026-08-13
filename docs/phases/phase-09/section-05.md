# Section 05 — HITL: Questions Queue & Approval Requests (7, 8)

## Objective

Build Screen 7 (Questions Queue — open questions across a human's in-flight tasks, with already-gathered context shown) and Screen 8 (Human Approval Requests — evidence bundle, decision buttons, timeout countdown), per §P. These are arguably the most operationally important screens in the entire UI, since they are where a human actually exercises the platform's core safety mechanism.

## Why It Exists

Every `ApprovalGate` and every human-facing requirements question (Phases 05–08) currently requires a human to run a CLI resume script — functional for engineering validation, but not how a real user (reviewer/deployer) would want to interact with the system day to day. This section is what turns Phase 08's `hitl_log` data into an actual, usable inbox.

## Expected Architecture

Screen 7 queries `list_pending_hitl(user_role)` (Phase 08 §01) filtered to `request_type="clarification"` (§B.2's `HITLRequest` discriminant — open requirements/scope questions, including any unresolved Section-06-of-Phase-06 `ClarificationEscalation` that reached HITL, not approval gates) across all of a user's tasks, showing enough context (already-gathered answers so far) that a human doesn't have to jump elsewhere to have enough information to answer. Screen 8 queries the same source filtered to `request_type="approval"` (with `policy_review`/`risk_approval` rows rendered alongside, same evidence-bundle pattern), rendering Phase 08 §02's evidence bundle in full, decision buttons matching the gate's `decision_options`, and a live timeout countdown derived from `hitl_log.timeout_at` (§R) — visually communicating the Fail-Closed timeout behavior (Phase 05 §02: timeout escalates, never auto-approves) so the human understands what happens if they don't act.

## Dependencies

Phase 08 §01 (`hitl_log` persistence, `list_pending_hitl`), Phase 08 §02 (evidence bundles), Section 01 (client plumbing).

## Atomic Implementation Tasks

1. Implement `GET /hitl/pending?role={role}` returning both clarification-type and approval-type pending requests, appropriately shaped for each screen.
2. Build Screen 7: a list of open questions across tasks, each showing enough already-answered context to answer without navigating away; submitting an answer calls the same resume mechanism as Screen 2.
3. Build Screen 8: full evidence bundle rendering (reusing Phase 08 §02's structure), decision buttons per the gate's `decision_options`, and a live countdown timer to `timeout_at`.
4. Implement the RBAC-aware filtering (§S) — a `developer` role sees only clarification requests they can answer; `reviewer`/`deployer`/`admin` additionally see approval requests appropriate to their role (e.g., `deployer`-only for production deployment approvals) — this is the first place RBAC (defined in §S but not yet enforced anywhere in the roadmap) becomes UI-visible; full backend RBAC *enforcement* is noted as a Phase 10/ongoing concern (the blueprint's own P1 list places "RBAC enforcement + audit log" alongside Phase 10's other post-MVP work) — this section renders role-appropriate views but should not be the sole enforcement point.
5. Integration test: with a task paused at both a clarification question and (a different task) an `ApprovalGate`, confirm Screen 7 and Screen 8 each show the correct pending item with correct context/evidence, and that responding via the UI correctly resumes each underlying graph.

## Manual Testing Procedure

1. Have two tasks in flight simultaneously — one paused on a clarification question, one paused on an approval gate — and confirm Screen 7/8 correctly separate and display them.
2. Respond to the clarification via Screen 7's UI and confirm the underlying graph resumes correctly (cross-check against Postgres).
3. Let an approval gate's countdown run down (using a short test-configured timeout) and confirm Screen 8 visually reflects the escalation rather than silently disappearing or auto-approving.

## Expected Demo

Screen recording of Screen 7 and Screen 8 each handling a real pending item, including responding to both via the UI and confirming the underlying tasks resume correctly — plus the timeout-countdown behavior shown explicitly.

## Acceptance Criteria

- [ ] Screen 7 correctly aggregates and displays open clarification questions across multiple in-flight tasks with sufficient context to answer.
- [ ] Screen 8 correctly renders the full evidence bundle and enforces the gate's exact `decision_options`.
- [ ] The timeout countdown is accurate and its escalation-not-auto-approval behavior is visually clear to the user.
- [ ] Responding via either screen correctly triggers the real `Command(resume=...)` round-trip, verified against Postgres state.

## Risks

- **Risk:** Presenting RBAC-filtered views in the UI without real backend enforcement could create a false sense of security (a user could still call the API directly and bypass role restrictions). **Mitigation:** explicitly document this section's RBAC handling as *presentation-layer* only at this phase, with backend enforcement tracked as a named future task — do not let the UI's filtering be mistaken for the real access control boundary.

## Future Improvements

- Full backend RBAC enforcement — Phase 10's stated post-MVP scope per the blueprint's own priority list (§T, P1).
- Slack-based HITL notifications as an alternative/complement to polling the UI — Phase 14.

## Research Opportunities

None.
