# Section 06 — Fan-In Coordinator, Clarification Escalation & Integration Validator

## Objective

Implement the Fan-in Coordinator (§D.4.1) — a **deterministic graph node, not an agent or LLM call** — that closes every `Send` fan-out: detecting file-level overlap *and* WCP-based semantic conflict, deciding merge vs. serialize-and-rerun, batching any `ClarificationEscalation`s into a bounded Implementation Manager replan (§D.9.3/§D.9.6), and finally handing off to the Integration Validator (§E.8), which verifies the merged result integrates correctly and catches interface mismatches.

## Why It Exists

Section 05's parallel fan-out is only safe because this section exists to catch what Section 04's decomposition-time ownership check might still miss in practice (e.g., a CodeGen agent touching a file outside its assigned scope while resolving an import, or two branches whose interfaces silently drifted apart even though their file sets never overlapped). §D.4.1 is explicit: overlapping or conflicting branches are serialized and re-run, never silently merged — this is a correctness-over-speed decision worth taking seriously. This section is also where the platform's largest documented communication gap (assumption drift discovered mid-implementation) gets closed, without opening any worker-to-worker channel to do it.

## Expected Architecture

The Fan-in Coordinator runs after all `Send`-dispatched branches complete — each branch having run `CodeGen → Validator(implementation)` per §D.4.0 — and LangGraph's native fan-in aggregates `SDLCState.implementation_results`, `worker_coordination_packets`, and `clarification_escalations`. It performs, in order, the decision list from §D.4.1:

1. **WCP selection** — highest `attempt_number` per `subtask_id` only.
2. **Overlap detection** — file sets from validated branches (`ImplementationResult.status="validated"`), cross-checked against WCP and Blackboard diffs.
3. **Semantic conflict detection** — deterministic rules from §D.4.1.1 (symbol normalization, direct match, substring fallback on assumptions, RI caller cross-check).
4. **Merge eligibility** — validated branches with neither issue merge into the integration worktree (§D.4.3).
5. **Serialize-and-rerun** — per §D.4.4: sequential redispatch, incremented `attempt_number`, full branch re-validation, Fan-in re-run.
6. **Replan batching** — any `needs_manager_attention=true` WCP or open `ClarificationEscalation` batched into **at most one** Implementation Manager replan pass.
7. **Integration Validator triggering** — once merge/serialize/replan resolve cleanly, dispatch to `Integration Validator`.

`Integration Validator` (High-capability tier, §E.8) then checks the *combined* diff set against interface contracts (using `get_callers`/`get_callees` from Phase 03 to verify no caller was left calling a now-changed signature incorrectly) and runs sandboxed integration tests where applicable.

## Dependencies

Section 05 (parallel diffs, `WorkerCoordinationPacket`s, `ClarificationEscalation`s to process), Section 04 (`BlackboardService`, `ReplanContext` assembly), Phase 03 (interface/call-graph queries).

## Atomic Implementation Tasks

1. Implement file-set overlap detection across validated `ImplementationResult` entries and their `worker_coordination_packets`.
2. Implement WCP-based semantic-conflict detection per §D.4.1.1 exactly — deterministic, no LLM calls.
3. Implement the serialize-and-rerun path per §D.4.4: sequential redispatch via `Command(goto=...)`, not a new `Send` fan-out; Fan-in re-runs after serialized branches re-validate.
4. Implement the merge step for eligible diffs (apply all diffs into a single integration branch/worktree).
5. Implement the replan-batching path: collect all `needs_manager_attention`/open `ClarificationEscalation`s from this fan-in round, assemble/pass the `ReplanContext` (Section 04), invoke the Implementation Manager for a single bounded replan pass, and route any unresolved item to HITL (`request_type="clarification"`) — enforce the ≤1-replan-per-group-per-attempt cap (§D.9.6) explicitly in code, not just by convention.
6. Implement `Integration Validator`: cross-check every changed symbol's callers (via `get_callers`) for signature compatibility, and run any available sandboxed integration tests against the merged branch.
7. Implement `FL-05` (§F.5): Integration Validator failure routes back to Implementation Manager for re-assignment, max 2×.
8. Integration test: deliberately construct a demo scenario where two CodeGen sub-tasks are dispatched with an artificially forced overlapping file, and confirm the serialize-and-rerun path triggers correctly rather than producing a silently broken merge; separately, construct a scenario with a genuine interface mismatch (one module changes a function signature another module calls) and confirm Integration Validator catches it.
9. Integration test: construct a scenario with **zero file overlap but a semantic conflict** (branch B's `assumptions` relies on a signature branch A's `interface_changes` altered) and confirm the WCP-based check (not file-overlap detection) is what catches it.
10. Integration test: force two `ClarificationEscalation`s in the same parallel group and confirm they are batched into exactly one Manager replan pass, not two separate ones.

## Manual Testing Procedure

1. Run the demo feature's normal (non-overlapping, non-conflicting) case and confirm clean fan-in merge and a passing Integration Validator.
2. Force an overlapping-edit scenario (e.g., manually configure two sub-tasks to target the same file) and confirm both diffs are discarded and re-run sequentially, with the final merged result being correct (not a silent conflict).
3. Force a semantic-conflict-without-file-overlap scenario and confirm the Coordinator catches it via WCP inspection alone.
4. Force a `ClarificationEscalation` and confirm it is batched to the Manager, resolved from RI/design where possible, and only reaches HITL when genuinely unresolvable from those sources.
5. Force an interface-mismatch scenario and confirm `FL-05` fires with a clear description of the mismatch.

## Expected Demo

Terminal walkthrough of the overlap-detection path (showing the discard + sequential re-run), the WCP-only semantic-conflict path, the clarification-escalation-to-replan path, and the interface-mismatch-catching path — these four are the section's key correctness proofs, more important than the "happy path" merge which is comparatively unremarkable.

## Acceptance Criteria

- [ ] Overlapping file edits across parallel branches are detected and never silently merged — always serialized and re-run.
- [ ] A semantic conflict with zero file overlap is caught via `WorkerCoordinationPacket` inspection, demonstrated with a dedicated test case distinct from the file-overlap test.
- [ ] `ClarificationEscalation`s from the same parallel group are batched into a single Manager replan pass, capped at one replan per group per attempt.
- [ ] Integration Validator correctly catches at least one deliberately constructed interface mismatch, using real call-graph data (Phase 03), not just pattern matching on diffs.
- [ ] `FL-05`'s 2× cap is enforced.
- [ ] No code path in this node makes an LLM call to resolve a conflict directly — every conflict resolution is either deterministic (serialize-and-rerun) or routed through the Manager/HITL, never an ad-hoc "ask a model to merge these diffs" step.

## Risks

- **Risk:** Overlap detection at file granularity may be too coarse (two agents editing different, non-conflicting parts of the same large file are treated as a conflict, wasting a re-run). **Mitigation:** start at file granularity (simplest, safest — favors correctness over throughput); the WCP-based semantic check (task 2 above) already narrows the other direction of the tradeoff (missing conflicts with no textual overlap), so file-level coarseness on its own is an acceptable, well-understood cost. Revisit granularity only if the false-positive rate (from Phase 15's future loop-trigger-rate KPI) proves it's a real throughput problem.
- **Risk:** An unbounded replan loop could form if replans keep flagging new issues. **Mitigation:** the ≤1-replan-per-group-per-attempt cap (§D.9.6) is enforced here as a hard code-level check, and a replan that still fails validation falls through to the normal `FL-04`/`FL-05` retry-count-bounded path, never a second ad-hoc coordination round.

## Future Improvements

- Finer-grained (symbol-level or AST-level) overlap detection, and any LLM-assisted pre-dispatch conflict prediction — documented as future roadmap only (§D.4.1), revisited once real conflict-rate data (Phase 15 KPIs) justifies the added complexity. Not scheduled into any phase.

## Research Opportunities

Measure the actual overlap rate and WCP-flagged-conflict rate across real tasks once enough decompositions run through this pipeline — if genuinely rare, this section's complexity is well-justified defensive engineering; if frequent, it's a signal Section 04's decomposition-time ownership resolution needs to be more conservative about what it considers "independent." Also worth tracking: what fraction of `ClarificationEscalation`s the Manager resolves from RI/design alone vs. how many reach HITL — a low HITL-reach rate validates the "RI-first, HITL-last" design; a high rate suggests the Manager needs richer inputs before Phase 10 formalizes routing.
