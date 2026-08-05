# Section 03 — Cost Kill-Switch & Budget Governance

## Objective

Implement the cost/token kill-switch described in §B.7: a wrapper mechanism that tracks per-task cost against `Task.budget` and force-routes any task exceeding budget (or a global max-node-visits count) to a human-escalation state, before any real agent exists to consume budget.

## Why It Exists

Cost governance must exist before Phase 02's model calls or Phase 05's agents start spending tokens — otherwise the very first agent built has no ceiling and a bug (infinite loop, runaway retries) has no backstop. Building it against a *simulated* cost source now (Section 04's sandbox execution time, or a fake token counter) proves the mechanism works before anything expensive depends on it.

## Expected Architecture

`packages/common/budget.py` exposes a `BudgetTracker` that:
- Accepts `(task_id, phase, agent_id, input_tokens, output_tokens, cost_usd)` records and persists them to `cost_tracking` (§R).
- Exposes `check_budget(task_id) -> BudgetStatus` (`ok | exceeded`) by summing recorded cost/tokens against `Task.budget`.
- Exposes a `KillSwitchError` raised when budget is exceeded — the calling code (in Phase 01's graph, later) is responsible for catching this and routing to `TaskState.BLOCKED` / human escalation, per Fail-Closed (Principle 8). This section does not build the graph-level routing (that's Phase 01) — it builds and unit-tests the pure budget-tracking and threshold logic in isolation.

## Dependencies

Section 01 (Task.budget), Section 02 (cost_tracking table).

## Atomic Implementation Tasks

1. Implement `BudgetTracker.record(...)` writing to `cost_tracking`.
2. Implement `BudgetTracker.check_budget(task_id)` — sums `cost_usd` and `input_tokens + output_tokens` for the task, compares against `Task.budget.cost_ceiling_usd` / `token_ceiling`.
3. Implement a global max-node-visits counter (a simple per-task visit count check) as a second, independent kill condition — this anticipates the "infinite feedback loop" risk from §N even though feedback loops don't exist until Phase 06.
4. Implement `Fail-Closed` behavior explicitly: if `check_budget` itself throws (e.g., DB unavailable), the caller must treat this as `exceeded`, never `ok` — write this as a documented contract and a unit test (mock the DB call to raise, assert the wrapper returns/raises the exceeded case).
5. Unit tests: budget within limit → `ok`; budget over limit → `exceeded`; budget-check failure → `exceeded` (fail-closed); recording is idempotent-safe for retried writes (no double-counting on a retried write with the same idempotency key — anticipates §J.3's idempotency pattern).

## Manual Testing Procedure

1. Create a `Task` with a low `cost_ceiling_usd` (e.g., `$0.01`).
2. Record several `BudgetTracker.record(...)` calls simulating cost until the ceiling is crossed.
3. Call `check_budget` and confirm it returns `exceeded`.
4. Query `cost_tracking` directly via `psql` to confirm every recorded row is present and summed correctly.

## Expected Demo

A CLI script (part of `scripts/demo_phase0.py`) printing the running total after each simulated cost record, then printing the moment `check_budget` flips to `exceeded`.

## Acceptance Criteria

- [ ] `check_budget` correctly sums cost and token usage across multiple recorded entries for a task.
- [ ] Exceeding either `cost_ceiling_usd` or `token_ceiling` alone (independently) triggers `exceeded`.
- [ ] A simulated internal failure of the check itself resolves to `exceeded`, not `ok` — unit-tested explicitly as a Fail-Closed proof point.
- [ ] Recording is safe against duplicate writes from retried calls with the same idempotency key.

## Risks

- **Risk:** Provider-reported cost fields may be inconsistent once real model calls exist (Phase 02) — building the tracker against a versioned internal pricing registry now (rather than trusting provider cost fields) avoids rework. **Mitigation:** design `BudgetTracker.record` to accept already-computed `cost_usd` from a pricing registry (built in Phase 02), not a provider's self-reported cost — note this explicitly so Phase 02 doesn't reintroduce provider-trust by accident.

## Future Improvements

- Per-phase cost breakdown dashboards — deferred to Phase 15 (Evaluation).

## Research Opportunities

None — this is intentionally deterministic, auditable logic per Principle 5.
