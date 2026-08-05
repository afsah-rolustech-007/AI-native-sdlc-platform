# Section 04 — Bug Validation Agent & Bug Protocol

## Objective

Implement the Bug Validation Agent (§E.8) and the full Bug Validation Protocol (§K.3): for `work_type` bug/hotfix, reproduce the reported bug **before** any fix agent runs; if not reproducible, return the task to Requirements for re-scoping rather than attempting a blind fix.

## Why It Exists

Fixing an unreproduced bug either does nothing (if the report was wrong) or masks a different, real problem (if the fix agent "fixes" some other issue that happens to look related). This protocol is what stops the platform from confidently producing a plausible-looking but wrong fix — directly serving Principle 5 (deterministic/auditable) by grounding the entire bug-fix flow in an actual, reproduced failure.

## Expected Architecture

`packages/agents/qa/bug_validation_agent.py`'s `BugValidationAgent(BaseAgent)` (High-capability tier, §E.8) runs *before* Phase 06's Implementation phase even starts for bug/hotfix work types — this is a re-entry point worth being precise about: the graph must route bug/hotfix tasks through Bug Validation immediately after Requirements/Design (design may be skipped entirely for hotfixes per §F.4, though that skip logic is formalized in Phase 10; for now, route conservatively through a minimal design step too). It takes the bug report + repo state, attempts to reproduce the described failure inside Phase 00's sandbox (writing a reproduction script/test case), and returns a `reproduced: bool` + reproduction artifact. Per §K.3: reproduced → proceed to Implementation with the reproduction case attached as the fix's acceptance test; not reproduced → route back to Requirements ("bug not reproducible as reported").

## Dependencies

Phase 06 (the Implementation phase this gates entry to), Phase 00 §04 (sandbox for reproduction attempts), Phase 05 (Requirements phase to route back to).

## Atomic Implementation Tasks

1. Implement `BugValidationAgent.attempt_reproduction(bug_report, repo) -> ReproductionResult` — generates a reproduction script/test case from the bug report's description and runs it in the sandbox against the current repo state.
2. Implement the routing logic: reproduced → attach reproduction artifact to `SDLCState`, proceed toward Implementation; not reproduced → route to `TaskState.REQUIREMENTS` with a clear reason logged (distinct from a normal Requirements re-entry — this needs its own log/flag so it's distinguishable in later audit).
3. Implement the fix-validation linkage (§K.3 step 3): once Phase 06 produces a fix, the same reproduction case must be re-run and must now pass — wire this as a required check the QA Manager (Section 01) invokes specifically for bug/hotfix tasks, not a generic test.
4. Implement regression-test generation from the reproduction case (§K.3 step 4): once the fix passes, commit the reproduction case itself as a permanent regression test (feeding `regression_history`, §R, for the first time with real data — directly benefiting Phase 06 §07's Feedback Agent, which was previously working with an empty episodic corpus).
5. Integration test: seed a real, reproducible bug into the demo repo; confirm Bug Validation reproduces it, the fix flow resolves it, and the re-validation + regression-test-commit steps complete correctly. Separately, seed a fabricated/non-reproducible bug report and confirm correct routing back to Requirements.

## Manual Testing Procedure

1. Seed a small, real bug into the demo repo (e.g., an off-by-one error) with a corresponding bug report description.
2. Run the task through Bug Validation and confirm reproduction succeeds with a sensible reproduction script.
3. Let the fix flow through Implementation (Phase 06) and confirm the QA Manager re-runs the reproduction case, confirms it now passes, and a regression test is committed.
4. Submit a bug report describing behavior that doesn't actually reproduce against the current repo; confirm correct routing back to Requirements with a clear "not reproducible" reason.

## Expected Demo

This section's demo *is* half of Phase 07's overall live demo (see README): the full seeded-bug walkthrough from reproduction through fix through regression-test commit, plus the non-reproducible-bug routing case shown separately.

## Acceptance Criteria

- [ ] A real, seeded bug is correctly reproduced before any fix is attempted.
- [ ] A non-reproducible bug report correctly routes back to Requirements, never silently proceeding to a blind fix attempt.
- [ ] The reproduction case is re-validated after the fix and correctly gates whether the fix is considered successful.
- [ ] A regression test is committed from the reproduction case, populating `regression_history` with real data for the first time.

## Risks

- **Risk:** Reproduction attempts for genuinely hard-to-reproduce bugs (timing-dependent, environment-specific) may produce false "not reproducible" results, incorrectly bouncing a real bug back to Requirements. **Mitigation:** document this as a known limitation of sandbox-based reproduction; a human reviewing the "not reproducible" routing (which, per fail-closed defaults, still requires review at this phase) is the current safety net — don't try to solve flaky/environment-dependent reproduction in this section.

## Future Improvements

- Broader environment simulation for harder-to-reproduce bug classes — a real future research area, not solved here.

## Research Opportunities

Track the reproduction success rate across real bug reports once volume exists — a low rate might indicate the reproduction agent needs richer sandbox capabilities (e.g., specific service dependencies) rather than a prompting fix.
