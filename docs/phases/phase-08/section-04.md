# Section 04 — PR Creation & Auto-Merge Policy

## Objective

Implement real PR creation against a git provider (a thin, local adapter at this phase — the full GitHub MCP integration is Phase 14; this section builds the adapter interface and a working implementation good enough to create real PRs now) and the auto-merge policy check per §B.6 (`risk_tier == Low` AND full QA suite green AND `confidence_score > AUTO_MERGE_CEILING`).

## Why It Exists

This is the platform's first action with real, external consequences — a PR that exists outside the platform's own database, visible to a human in their normal git workflow. Building the adapter interface now (even before Phase 14's full MCP integration) is what lets Phase 14 later swap in the official GitHub MCP server as a drop-in replacement, per the same adapter-seam discipline used for models (Phase 02) and repository intelligence (Phase 03).

## Expected Architecture

`packages/mcp_integrations/base.py`'s `GitProviderAdapter` Protocol (`create_pr`, `merge_pr`, `get_pr_status`) is implemented by a `LocalGitAdapter` at this phase — using the git CLI directly against a real (possibly self-hosted or a personal GitHub/GitLab repo used for development) remote, sufficient to prove the flow end-to-end without waiting for Phase 14. Auto-merge policy (§B.6) is implemented as an explicit, testable function `is_auto_merge_eligible(task) -> bool` — structurally correct now, but practically **unreachable** until Phase 10's real risk/confidence routing exists (the fail-closed default profile from `roadmap.md` §2.4 never actually classifies a task as eligible yet) — document this explicitly so it isn't mistaken for a currently-active autonomous behavior.

## Dependencies

Section 03 (approved, reviewed diff), Phase 00 (config for git credentials — least-privilege, task-scoped, per §B.6).

## Atomic Implementation Tasks

1. Implement the `GitProviderAdapter` Protocol.
2. Implement `LocalGitAdapter` using git CLI operations (or a lightweight REST call to a real provider) for PR creation from the task's implementation branch.
3. Implement least-privilege, task-scoped credential handling for git operations (§B.6) — never a long-lived, broadly-scoped token; document the credential-scoping approach explicitly even if the "short-lived" mechanics are simplified at this phase pending a real provider integration in Phase 14.
4. Implement `is_auto_merge_eligible(task) -> bool` per §B.6's exact condition, unit-tested against synthetic inputs (Low-risk+green-QA+high-confidence → true; any other combination → false) — since real routing can't produce a true case yet, this is tested in isolation, not via a live end-to-end run.
5. Wire PR creation into the graph flow after `ApprovalGate`(pr) approval; wire the (currently always-false-in-practice) auto-merge check as a documented bypass path for future use.
6. Implement idempotency (§J.3) for PR creation specifically: a retried/resumed graph execution must not create a duplicate PR for the same task — use an idempotency key derived from `task_id` stored before the call, checked before retrying.
7. Integration test: the demo feature creates a real PR after approval; a simulated retry (re-invoking the same node after a forced failure) does not create a second PR.

## Manual Testing Procedure

1. Run the demo feature through to PR creation and confirm a real PR appears against the configured git remote.
2. Force a retry of the PR-creation step and confirm no duplicate PR is created.
3. Unit-test `is_auto_merge_eligible` directly with synthetic inputs covering all boundary conditions.

## Expected Demo

A real PR link (or screenshot) created by the platform for the demo feature, plus a printed confirmation that a forced retry did not duplicate it.

## Acceptance Criteria

- [ ] A real PR is created against a real git remote for an approved task.
- [ ] PR creation is idempotent under retry — verified by an explicit forced-retry test.
- [ ] `is_auto_merge_eligible` is correctly implemented and unit-tested, while explicitly documented as currently unreachable in practice pending Phase 10.
- [ ] Git credentials used are task-scoped and least-privilege, not a shared broad-access token.

## Risks

- **Risk:** Building against a `LocalGitAdapter` now, ahead of Phase 14's MCP integration, risks the interface not actually matching what the GitHub MCP server naturally provides. **Mitigation:** design `GitProviderAdapter`'s method signatures around the *conceptual* operations (create/merge/status), not around git-CLI-specific mechanics, so Phase 14 swapping in the MCP-based implementation is a genuine adapter swap, not a redesign — apply the same discipline that made Phase 02's model swap and Phase 03's graph-DB swap clean.

## Future Improvements

- Full GitHub MCP server integration — Phase 14 (drop-in adapter replacement).
- Real auto-merge activation — becomes reachable once Phase 10's real risk/confidence routing exists.

## Research Opportunities

None yet.
