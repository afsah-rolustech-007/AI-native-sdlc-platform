# Section 04 — Crash Recovery Test Harness

## Objective

Build an automated test harness that runs the stub graph, kills the worker process at a randomized point mid-execution, restarts it, and verifies the task resumes correctly — repeated across many trials — to produce the specific, numeric completion criterion the blueprint sets for this phase: **100% success across 20 crash trials.**

## Why It Exists

"It probably survives a crash" is not an acceptable engineering standard for a platform whose entire safety model depends on durable checkpointing. This section converts that assumption into a repeatable, automated, numeric proof — and gives every later phase a harness pattern to reuse when chaos-testing their own additions (Phase 16 generalizes this pattern considerably).

## Expected Architecture

`tests/chaos/test_crash_recovery.py` spawns the worker as a subprocess, sends a task through the graph, kills the subprocess (`SIGKILL`, not a graceful shutdown — the whole point is testing the ungraceful case) at a randomized delay within the expected execution window, restarts the worker, and polls until the task reaches a terminal state (or the resume script is invoked, depending on whether Section 03's interrupt is in the execution path for the trial). Assertions: final state is correct and complete; no duplicate node executions occurred beyond what idempotent re-entry into a node would produce; no orphaned resources (sandbox containers from Phase 00 — though none are used by stub nodes yet, so this becomes fully relevant again once Phase 06 uses the sandbox mid-graph).

## Dependencies

Section 02 (durable checkpoint to resume from), Section 03 (optional — some trials should kill before/after the interrupt point specifically, to test both branches).

## Atomic Implementation Tasks

1. Implement subprocess-based worker launch/kill utilities for the test harness.
2. Implement randomized kill-timing: some trials kill before any node runs, some mid-node-sequence, some exactly at the `interrupt()` point, some after resume but before completion.
3. Implement post-kill restart + resume logic (auto-resume for non-interrupted trials; scripted `Command(resume=...)` for interrupted trials).
4. Implement the correctness assertion: compare the final `SDLCState`/`agent_events` against the expected fully-completed trace shape (same 8 nodes present, in order, no duplicates beyond what's explicitly tolerated).
5. Run the harness for 20 trials in a loop; log pass/fail and kill-timing per trial to a results file.
6. Wire this harness into CI as a slower, separate job (not on every push — e.g., nightly or pre-merge-to-main) given its runtime cost.

## Manual Testing Procedure

1. Run `pytest tests/chaos/test_crash_recovery.py -v` locally.
2. Inspect the per-trial log for kill-timing diversity (confirm trials aren't clustering at only one point in execution).
3. Deliberately introduce a bug (e.g., skip a checkpoint write) and confirm the harness actually catches it — a chaos test that can't fail is worthless; prove it can.

## Expected Demo

A results table (printed or saved) showing 20/20 trials passed, with the randomized kill-timing per trial listed — proving both breadth of coverage and the numeric target.

## Acceptance Criteria

- [ ] 20/20 trials pass with correct, complete final state after crash + restart, matching the blueprint's explicit Phase 1 completion criterion.
- [ ] Kill timings are randomized and cover: pre-first-node, mid-sequence, at-interrupt, post-resume.
- [ ] The harness is demonstrated to actually detect a deliberately introduced regression (mutation-test-style self-check).
- [ ] No orphaned processes/connections after the full 20-trial run.

## Risks

- **Risk:** A harness that's flaky for reasons unrelated to the system under test (e.g., subprocess timing races in the test itself) erodes trust in the whole chaos-testing practice going forward. **Mitigation:** keep kill-timing based on explicit, controllable signals (e.g., a debug hook that signals "node N about to start") rather than wall-clock sleep guesses, so the harness itself is deterministic even though the graph state exploration is randomized.

## Future Improvements

- Generalize this harness pattern for Postgres-failover and queue-load chaos tests in Phase 16 — this section's harness is the template, not a one-off.

## Research Opportunities

None — but the pattern established here (deterministic hooks + randomized exploration) is worth explicitly documenting in `development_strategy.md`'s decisions log for reuse.
