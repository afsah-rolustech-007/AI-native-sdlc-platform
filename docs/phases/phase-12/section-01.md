# Section 01 — Context Budget Math per Phase

## Objective

Implement `ContextBudget` exactly per §H.1: model-window-derived token allocations (`SYSTEM_PROMPT`, `OUTPUT_RESERVE`, `CONVERSATION_HOT`, `ARCH_SUMMARY` reservations, then `PHASE_BUDGETS` per phase), and wire every agent's context assembly (used informally since Phase 05) to respect these hard caps.

## Why It Exists

Every agent since Phase 05 has assembled context reasonably but without an explicit ceiling — this worked at small scale (Phase 03–10's fixture repo) but is exactly the assumption Phase 11's scale would strain. Making the budget explicit and enforced is what turns "context is probably fine" into a hard, testable guarantee.

## Expected Architecture

`packages/context_engine/budget.py` implements `ContextBudget` per §H.1's exact structure and numbers (documented as tied to the current model's context window — `MODEL_MAX` must be read from the active `ModelAdapter`'s capability metadata, not hardcoded, so a future model swap, Phase 16, doesn't silently invalidate these numbers). `BaseAgent.build_context()` (Phase 05 §01) is updated to look up its phase's `PHASE_BUDGETS` entry and enforce it — assembled context exceeding budget triggers Section 03's compression pipeline before the model call, not after (avoiding wasted spend on an over-budget call that would need truncation/retry anyway).

## Dependencies

Phase 05 §01 (`BaseAgent.build_context()` to retrofit), Phase 02 (`ModelAdapter` capability metadata for `MODEL_MAX`).

## Atomic Implementation Tasks

1. Implement `ContextBudget` per §H.1, deriving `MODEL_MAX` from the active adapter rather than a hardcoded constant.
2. Implement per-phase budget lookup and enforcement inside `BaseAgent.build_context()`.
3. Add an explicit "actual context used" metric to every agent's OTel trace event (feeding §L.2's "Context efficiency (used/retrieved)" KPI, which Phase 15 will consume) — this section is what makes that future KPI measurable.
4. Retrofit every existing agent (Planning Manager, Requirements Analyst, Design Manager, CodeGen, QA agents, Review/Release agents — the full roster built across Phases 05–08) to report against this budget, and identify (via the new metric) any agent currently assembling meaningfully over-budget context.
5. Unit tests: budget calculation matches §H.1's arithmetic exactly; an agent's context assembly exceeding its phase budget correctly triggers the compression path (verified once Section 03 exists — this section's tests can initially assert "triggers a documented over-budget signal," with Section 03 wiring the actual compression response).

## Manual Testing Procedure

1. Run the demo feature through several agents and inspect the new "tokens used vs. budgeted" metric in traces.
2. Identify which (if any) existing agents were assembling meaningfully over-budget context before this section's enforcement.
3. Confirm `MODEL_MAX` correctly reflects the active adapter's real context window, not a stale hardcoded value.

## Expected Demo

A trace-derived report across the full agent roster showing tokens-used-vs-budgeted per phase, highlighting any agents that needed adjustment as a result of this section's new visibility.

## Acceptance Criteria

- [ ] `ContextBudget` matches §H.1's exact structure, with `MODEL_MAX` correctly sourced from the live adapter.
- [ ] Every agent's context assembly is measured against its phase's budget, with the measurement visible in traces.
- [ ] At least one previously-unmeasured over-budget assembly pattern (if any existed) is identified and documented.

## Risks

- **Risk:** Retrofitting budget enforcement onto agents built across five prior phases (05–08) without careful testing could subtly change their behavior (e.g., silently truncating context they relied on). **Mitigation:** re-run every existing agent's integration tests after this retrofit, same discipline as Phase 10 §04's large refactor.

## Future Improvements

- Per-agent budget tuning based on real usage data — a natural Phase 15 follow-on once efficiency KPIs exist.

## Research Opportunities

None directly in this section — it's measurement infrastructure; the research payoff comes in Section 05's benchmark.
