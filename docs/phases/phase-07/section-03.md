# Section 03 — Unit/Integration Test Agent

## Objective

Implement the Unit/Integration Test Agent (§E.8: runs and extends test coverage, impact-analysis scoped) — the agent that actually executes `pytest` against Section 02's computed scope and, where coverage is thin, generates new tests.

## Why It Exists

Running existing tests answers "did I break something known." Extending coverage where it's thin is what starts closing the gap on "did I verify the new behavior at all" — directly relevant since Phase 06's CodeGen agents don't yet write their own tests as a required output.

## Expected Architecture

`packages/agents/qa/unit_test_agent.py`'s `TestAgent(BaseAgent)` (Fast tier, §E.8) runs `pytest` (Phase 00's sandbox) against Section 02's `TestScope`, parses results, and — for changed code lacking direct test coverage — proposes new test cases (a lighter-weight version of §K.4's full regression-test-generation pipeline, which is formalized in Phase 13; this section's version is scoped to "cover what QA just saw," not the full post-QA regression harvesting).

## Dependencies

Section 02 (`TestScope`), Phase 00 §04 (sandbox for running tests).

## Atomic Implementation Tasks

1. Implement sandboxed `pytest` execution against a computed scope, parsing pass/fail/skip results into `QAEvidence`'s shape.
2. Implement coverage-gap detection (e.g., via `pytest-cov` on the scoped run) to identify changed lines without test coverage.
3. Implement new-test proposal generation for identified gaps — a Fast-tier LLM call producing pytest-formatted test cases, validated (they must actually run, and ideally fail-before/pass-after against the diff — a mini reproduce-then-verify pattern worth adopting here too) before being accepted.
4. Implement `FL-06` routing (spec/test failure → Implementation phase, max 3×) for genuine test failures (as opposed to the coverage-extension path, which doesn't route failure, just adds tests).
5. Integration test: the demo feature's scoped tests run and pass; a deliberately under-tested change (a new function with no direct test) triggers a proposed new test that correctly exercises it.

## Manual Testing Procedure

1. Run the demo feature's QA and confirm scoped tests execute and results populate `QAEvidence`.
2. Review a proposed new test for a coverage gap — confirm it's a meaningful test, not a trivial no-op assertion.
3. Force a test failure and confirm `FL-06` routes back to Implementation with specific failure details.

## Expected Demo

Terminal output showing scoped test execution results, followed by a proposed new test for an identified coverage gap, with the proposed test shown actually running (and passing) against the current diff.

## Acceptance Criteria

- [ ] Scoped test execution correctly reports pass/fail/skip into `QAEvidence`.
- [ ] Proposed new tests are validated to actually run correctly (not just syntactically plausible) before being accepted into the codebase.
- [ ] `FL-06` fires correctly on genuine test failure, with a 3× cap.

## Risks

- **Risk:** LLM-generated tests can be superficially plausible but tautological (asserting on the implementation's own output rather than an independent expectation). **Mitigation:** where feasible, derive expected values from the requirements/spec rather than from re-running the implementation and asserting on whatever it returns — a real quality bar worth holding even at this early phase, since sloppy generated tests actively erode trust in QA evidence.

## Future Improvements

- Full regression-test-generation pipeline tied to bug fixes and exploratory findings (§K.4) — Phase 13.

## Research Opportunities

Compare the quality (mutation-kill rate, once Phase 13's mutation testing exists) of LLM-proposed tests from this section against human-written tests in the same codebase — a good early signal of whether this capability needs a different prompting strategy or model tier.
