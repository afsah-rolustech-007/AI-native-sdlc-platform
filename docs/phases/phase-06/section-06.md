# Section 06 — Fan-In Conflict Detection & Integration Validator

## Objective

Implement the fan-in aggregator node (§D.4) that checks for overlapping file edits across parallel CodeGen branches before merging — serializing and re-running overlapping branches rather than silently merging — and the Integration Validator (§E.8) that verifies the merged result integrates correctly and catches interface mismatches.

## Why It Exists

Section 05's parallel fan-out is only safe because this section exists to catch what Section 04's decomposition-time ownership check might still miss in practice (e.g., a CodeGen agent touching a file outside its assigned scope while resolving an import). §D.4 is explicit: overlapping branches are serialized and re-run, never silently merged — this is a correctness-over-speed decision worth taking seriously.

## Expected Architecture

The fan-in node runs after all `Send`-dispatched CodeGen branches complete (LangGraph's native fan-in over `SDLCState.implementation_results`), and before treating the diffs as final: it computes the file sets touched by each branch's diff, checks for overlaps, and for any overlapping pair, discards both diffs and re-dispatches them *sequentially* (second branch now sees the first's already-applied change) rather than merging conflicting edits automatically. Once no overlaps remain, `Integration Validator` (High-capability tier, §E.8) checks the *combined* diff set against interface contracts (using `get_callers`/`get_callees` from Phase 03 to verify no caller was left calling a now-changed signature incorrectly) and runs sandboxed integration tests where applicable.

## Dependencies

Section 05 (parallel diffs to merge/validate), Phase 03 (interface/call-graph queries).

## Atomic Implementation Tasks

1. Implement file-set overlap detection across `implementation_results` entries.
2. Implement the serialize-and-rerun path: on detected overlap, discard the overlapping diffs, re-dispatch them as a sequential (non-`Send`, ordinary sequential node) pair, second-after-first.
3. Implement the merge step for non-overlapping diffs (apply all diffs into a single integration branch/worktree).
4. Implement `Integration Validator`: cross-check every changed symbol's callers (via `get_callers`) for signature compatibility, and run any available sandboxed integration tests against the merged branch.
5. Implement `FL-05` (§F.5): Integration Validator failure routes back to Implementation Manager for re-assignment, max 2×.
6. Integration test: deliberately construct a demo scenario where two CodeGen sub-tasks are dispatched with an artificially forced overlapping file, and confirm the serialize-and-rerun path triggers correctly rather than producing a silently broken merge; separately, construct a scenario with a genuine interface mismatch (one module changes a function signature another module calls) and confirm Integration Validator catches it.

## Manual Testing Procedure

1. Run the demo feature's normal (non-overlapping) case and confirm clean fan-in merge and a passing Integration Validator.
2. Force an overlapping-edit scenario (e.g., manually configure two sub-tasks to target the same file) and confirm both diffs are discarded and re-run sequentially, with the final merged result being correct (not a silent conflict).
3. Force an interface-mismatch scenario and confirm `FL-05` fires with a clear description of the mismatch.

## Expected Demo

Terminal walkthrough of the overlap-detection path (showing the discard + sequential re-run) and the interface-mismatch-catching path — both are the section's key correctness proofs, more important than the "happy path" merge which is comparatively unremarkable.

## Acceptance Criteria

- [ ] Overlapping file edits across parallel branches are detected and never silently merged — always serialized and re-run.
- [ ] Integration Validator correctly catches at least one deliberately constructed interface mismatch, using real call-graph data (Phase 03), not just pattern matching on diffs.
- [ ] `FL-05`'s 2× cap is enforced.

## Risks

- **Risk:** Overlap detection at file granularity may be too coarse (two agents editing different, non-conflicting parts of the same large file are treated as a conflict, wasting a re-run) or too fine (line-level detection missing semantic conflicts that don't textually overlap). **Mitigation:** start at file granularity (simplest, safest — favors correctness over throughput per §D.4's own stated preference); revisit granularity only if the false-positive rate (from Phase 15's future loop-trigger-rate KPI) proves it's a real throughput problem.

## Future Improvements

- Finer-grained (symbol-level, not file-level) overlap detection — worth exploring once real conflict-rate data exists.

## Research Opportunities

Measure the actual overlap rate across real tasks once enough decompositions run through this pipeline — if genuinely rare, this section's complexity is well-justified defensive engineering; if frequent, it's a signal Section 04's decomposition-time ownership resolution needs to be more conservative about what it considers "independent."
