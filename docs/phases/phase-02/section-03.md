# Section 03 — Cost Tracking, Pricing Registry & Usage Telemetry

## Objective

Implement the versioned pricing registry (§I.5) and a usage telemetry callback that intercepts every `ModelAdapter` call's reported usage, converts it to cost via the registry, and feeds it into Phase 00's `BudgetTracker` and OTel tracer — closing the loop between "an LLM call happened" and "it's auditable and budget-checked."

## Why It Exists

The blueprint is explicit: "Never rely on provider-reported cost fields alone — not consistently available across providers" (§I.5). A versioned, internal pricing registry is what makes cost auditable and comparable across providers (relevant again in Phase 16 when a second provider is added). This section is also what makes Phase 00's kill-switch (built against a *simulated* cost source) finally load-bearing against *real* cost.

## Expected Architecture

`packages/model_adapters/registry.py` holds a versioned mapping `{model_id: ModelPricing}`, loaded from a config file (anticipates `configs/pricing/` per §Q) so price updates don't require a code deploy. `packages/model_adapters/telemetry.py` wraps every adapter call: on response, reads `usage.input_tokens`/`usage.output_tokens` from the raw response, looks up pricing by `model_id`, computes `cost_usd`, and calls `BudgetTracker.record(...)` (Phase 00 §03) and `TelemetrySink.start_span/end_span` with `kind="llm_call"` (Phase 00 §05). Do not import OpenTelemetry here.

## Dependencies

Section 02 (a real adapter to wrap), Phase 00 Sections 03 and 05 (budget tracker, tracer).

## Atomic Implementation Tasks

1. Implement `ModelPricing` loading from a `configs/pricing/registry.yaml` (or `.json`) file — human-editable, PR-reviewed per §N's "policy changes deployed without review" mitigation.
2. Implement `compute_cost(usage, pricing) -> float`.
3. Implement the telemetry wrapper — likely as a decorator or a LangChain callback handler attached to every `GLMAdapter` call — that fires on every completion/stream/tool-call/embed response.
4. Wire the wrapper to call `BudgetTracker.record(task_id, phase, agent_id, ...)` — note that `task_id`/`phase`/`agent_id` don't have a natural source yet at this phase (no agents exist) — thread them through as explicit parameters on the wrapped call for now; Phase 05 will supply them from real agent context.
5. Wire the same wrapper to emit an `llm_call` span via `TelemetrySink`, populating `model_id`, `provider`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `operation`.
6. Unit test: mock adapter response with known usage, assert `compute_cost` matches hand-calculated expected value; assert `BudgetTracker.record` and `TelemetrySink.end_span` are both called with correct arguments. Grep: `model_adapters/` has no `opentelemetry` import.

## Manual Testing Procedure

1. Make a real GLM call through the telemetry wrapper.
2. Query `cost_tracking` and confirm a row exists with realistic, non-zero `input_tokens`/`output_tokens`/`cost_usd`.
3. Confirm the `llm_call` span for this call has `model_id` populated (unlike Phase 00's sandbox-only spans).
4. Manually edit the pricing registry file, re-run, and confirm the computed cost changes accordingly (proving it's config-driven, not hard-coded).

## Expected Demo

This section's demo *is* Phase 02's overall live demo (see Phase 02 README): a live GLM call followed by a printed `cost_tracking` row, proving the full call→cost→audit path.

## Acceptance Criteria

- [ ] Cost is computed from the internal pricing registry, never from a provider-reported cost field.
- [ ] Pricing registry is externally configurable (file-based) without a code change.
- [ ] Every real model call produces exactly one `cost_tracking` row and one `llm_call` span with correctly populated usage fields.
- [ ] `BudgetTracker.check_budget` (Phase 00 §03) correctly reflects real LLM spend when queried after a real call.

## Risks

- **Risk:** Pricing registry going stale as providers change prices. **Mitigation:** version the registry file (e.g., a `version`/`effective_date` field) and treat updates as routine, reviewed changes — not a design problem to solve now.

## Future Improvements

- Per-phase/per-agent cost dashboards — Phase 15.

## Research Opportunities

None.
