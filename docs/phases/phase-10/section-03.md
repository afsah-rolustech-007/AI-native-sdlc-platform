# Section 03 — escalate_model_tier() & Model Router Integration

## Objective

Implement `escalate_model_tier()` per §F.3 — escalation-on-repeated-rejection, upgrading a node's model tier when validators repeatedly reject its output, routing to the Feedback Agent (and then HITL) when retries are exhausted — and integrate it with Phase 02 §04's basic `ModelRouter`.

## Why It Exists

Phase 02 deliberately deferred this exact logic, noting it needed real validator-rejection data to integrate correctly. That data now exists from Phases 05–07's real `Validator` instances. This closes the loop on the model-routing story: `ModelRouter.select()` picks a starting tier by capability requirement (Phase 02); `escalate_model_tier()` adjusts it upward under real observed friction.

## Expected Architecture

`packages/workflow_engine/policy.py`'s `escalate_model_tier(node_state) -> ModelTier` implements §F.3's exact logic: 2+ rejections at `FAST_CHEAP` → `BALANCED`; 2+ rejections at `BALANCED` → `FRONTIER`; rejections reaching `max_retries_per_node` → route to Feedback Agent (Phase 06 §07), then HITL if still failing (Fail-Closed). `NodeExecutionState` (tracking `validator_rejections`, current `model_tier` per node invocation) is a new, small piece of per-node tracking state — implement it as an addition to the agent execution context (not full `SDLCState`, to avoid bloating checkpoint size, consistent with §B.3's "Working memory only in graph state" principle — though this specific tracking is arguably legitimate working memory; document the placement decision).

## Dependencies

Section 02 (`WorkflowProfile.model_tier` as the starting point), Phase 06 §07 (Feedback Agent to route to on exhaustion), Phase 02 §04 (`ModelRouter`).

## Atomic Implementation Tasks

1. Implement `NodeExecutionState` tracking (rejection count, current tier) scoped correctly (per node invocation across retries within one task, not globally).
2. Implement `escalate_model_tier()` per §F.3's exact thresholds.
3. Wire `BaseAgent.run()` (Phase 05 §01) to consult `escalate_model_tier()` before each retry attempt, using its result to select the model via `ModelRouter` instead of a fixed tier.
4. Wire the "reaching max_retries → Feedback Agent → HITL if still failing" path to Phase 06 §07's actual Feedback Agent invocation (rather than the earlier phase's simpler "3 consecutive failures on same module" trigger — reconcile the two: `escalate_model_tier()`'s per-node retry exhaustion and Phase 06 §07's Feedback Agent trigger are closely related but were specified in different parts of the blueprint; ensure both correctly funnel into the same Feedback Agent without duplicate/conflicting triggering).
5. Unit tests: rejection counts correctly drive tier escalation at both thresholds; retry exhaustion correctly routes to Feedback Agent; a still-failing Feedback Agent output correctly escalates to HITL (re-verifying Phase 06 §07's existing test, now via this section's real trigger path instead of the phase's earlier standalone implementation).

## Manual Testing Procedure

1. Force a CodeGen sub-agent (Phase 06 §05) to fail validation twice at `FAST_CHEAP` tier and confirm the third attempt runs at `BALANCED`.
2. Force continued failure at `BALANCED` and confirm escalation to `FRONTIER`.
3. Force failure through full retry exhaustion and confirm the Feedback Agent activates, and — if forced to fail again — HITL escalation fires.

## Expected Demo

Terminal walkthrough of a forced escalation sequence: `FAST_CHEAP` → rejection → rejection → `BALANCED` → rejection → rejection → `FRONTIER` → retry exhaustion → Feedback Agent → (forced) still fails → HITL — the complete escalation ladder from §F.3 shown firing correctly end to end.

## Acceptance Criteria

- [ ] `escalate_model_tier()` matches §F.3's exact thresholds and behavior.
- [ ] Escalation is correctly triggered by real validator rejections from Phases 05–07's actual `Validator` instances.
- [ ] Retry exhaustion correctly and exclusively funnels into the Feedback Agent (no duplicate/conflicting trigger paths left over from Phase 06 §07's earlier, simpler implementation).
- [ ] The full escalation ladder (tier-up, tier-up, Feedback Agent, HITL) is demonstrated working end to end.

## Risks

- **Risk:** Reconciling Phase 06 §07's original Feedback Agent trigger (a standalone "3 consecutive failures" counter) with this section's more general `escalate_model_tier()`-driven trigger risks either double-triggering or a gap where neither fires. **Mitigation:** treat this reconciliation as a first-class task (task 4) with its own explicit test, not an assumed-compatible merge.

## Future Improvements

- Cost-aware escalation (weighing tier upgrade cost against task budget remaining) — a reasonable refinement once Phase 15's cost-efficiency KPIs exist to inform the tradeoff.

## Research Opportunities

Track how often escalation actually resolves a failure (tier-up leads to a subsequent pass) versus how often it doesn't (failure persists even at `FRONTIER`, ultimately reaching Feedback Agent/HITL anyway) — a strong signal, once enough data exists (Phase 15), of whether the escalation ladder is well-calibrated or whether some failure classes should skip straight to Feedback Agent.
