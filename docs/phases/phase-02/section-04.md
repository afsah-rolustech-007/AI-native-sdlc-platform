# Section 04 — Basic Model Router & Circuit Breaker

## Objective

Implement a minimal `ModelRouter.select(phase, operation, context)` that looks up the `CAPABILITY_REQUIREMENTS` table (§I.2) and returns the cheapest available model meeting the requirement, plus the circuit-breaker pattern (§I.3) for provider unavailability — deliberately *not* implementing `escalate_model_tier()`'s rejection-count logic yet, since that requires real validator rejection data that doesn't exist until Phase 06.

## Why It Exists

Agents (Phase 05+) need *some* way to pick a model without hardcoding "always use GLM-4.7" into every call site — that would defeat the purpose of Phase 02 the moment it's used. A basic capability-lookup router, built now, is what Phase 05's agents call from day one; Phase 10 later extends it with the full escalation/routing-profile logic once workflow profiles exist.

## Expected Architecture

`packages/model_adapters/router.py` implements `ModelRouter.select(phase: str, operation: str, context: dict) -> ModelAdapter` by looking up `CAPABILITY_REQUIREMENTS[(phase, operation)]` and returning the cheapest registered adapter whose `capability_score >= required`. `CircuitBreaker` wraps adapter calls: on repeated failures/errors from a provider, flips to an "open" state, and any task attempting a call is checkpointed and paused (not failed) per §I.3 — this hooks into Phase 01's `interrupt`/pause machinery conceptually, though full integration with a real graph node happens once Phase 05 wires a real agent node that calls the router.

## Dependencies

Section 02 (a real adapter to select), Section 03 (telemetry to detect failure rates for the breaker).

## Atomic Implementation Tasks

1. Implement the `CAPABILITY_REQUIREMENTS` table from §I.2 as a versioned, importable constant (`configs/` file or a Python constant — decide based on how often it's expected to change; a Python constant is fine at MVP since it's not yet driven by empirical data).
2. Implement `ModelRouter.select()` — with only one provider (GLM, two tiers) registered at this phase, the "cheapest meeting requirement" logic is almost trivial, but must be written generically (loop over registered adapters, not an if/else on a known single provider) since Phase 16 adds a second provider and the logic must not need rewriting.
3. Implement `CircuitBreaker` with a configurable error-rate threshold and open/half-open/closed states.
4. Implement the "pause, don't fail" behavior contract: document (and stub-test against a fake node) that when the breaker is open, the correct caller behavior is to raise a distinguishable exception type that graph code (Phase 05+) will catch and route to a paused state — this section defines and unit-tests the exception/contract; actual graph-level pause wiring happens when a real node calls this router.
5. Unit tests: `select()` returns the cheapest adapter meeting a given capability score; `select()` raises clearly when no registered adapter meets a requirement (fail-closed — never silently returns an under-capable model); circuit breaker opens after threshold breaches and the "half-open" recovery path is tested with a simulated recovered call.

## Manual Testing Procedure

1. Call `ModelRouter.select("implementation", "code_generation", {})` and confirm it returns the GLM fast/flash tier (score 6 requirement, per §I.2).
2. Call `ModelRouter.select("design", "architecture", {})` and confirm it returns the higher-capability tier (score 9 requirement).
3. Simulate repeated adapter failures (mock the adapter to raise) and confirm the circuit breaker opens after the configured threshold.
4. Simulate a recovered call after the breaker is open and confirm it transitions to half-open/closed correctly.

## Expected Demo

Terminal output showing two different `ModelRouter.select()` calls returning two different capability tiers for two different `(phase, operation)` pairs from §I.2's table, followed by a simulated failure sequence showing the circuit breaker's state transitions printed at each step.

## Acceptance Criteria

- [ ] `ModelRouter.select()` correctly implements the capability-lookup logic from §I.2 for at least the two GLM tiers.
- [ ] `select()` fails closed (raises, never silently downgrades) when no adapter meets the required capability score.
- [ ] Circuit breaker correctly transitions through open/half-open/closed states under simulated failure and recovery.

## Risks

- **Risk:** Building router logic too early risks needing significant rework once Phase 10's `resolve_workflow_profile()` and `escalate_model_tier()` exist. **Mitigation:** explicitly scope this section's router to *capability lookup only* — resist the temptation to bolt on escalation-on-rejection logic here; that belongs in Phase 10 where it can be correctly integrated with `WorkflowProfile`.

## Future Improvements

- `escalate_model_tier()` (§F.3) — Phase 10, once validator-rejection data exists.
- Multi-provider selection with cost-optimization across providers — Phase 16, once a second provider exists.

## Research Opportunities

None yet — becomes relevant once real routing decisions have outcome data to evaluate against (Phase 15).
