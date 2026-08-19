# Section 05 — TelemetrySink & OTel Adapter

## Objective

Stand up the application telemetry contract in §B.8: `TelemetrySink` (no OpenTelemetry imports) plus `OtelTelemetrySink` in `packages/common/tracing.py`. Prove failure isolation using sandbox runs from Section 04 as the first real spans.

## Why It Exists

Debuggability across 17 phases depends on this existing from day one. Evaluation (§L) later consumes the same contract — if Phase 00 emits LangGraph-specific or Langfuse-SDK calls, Phase 15 cannot stay orchestrator-independent. Retrofitting after agents exist means re-instrumenting every node.

## Expected Architecture

`packages/common/telemetry.py` defines `TelemetrySink` (`start_span` / `end_span` / `emit_event` / `record_metric` / `span` context manager) per §B.8.3. Every method **never raises**.

`packages/common/tracing.py` implements `OtelTelemetrySink`: tracer provider, console span exporter (dev), OTLP exporter (optional Langfuse/collector). Map MVP attributes (§B.8.4). Bind `task_id` and `trace_id` into `structlog` via `contextvars`.

Keep `emit_node_event(...)` as a compatibility helper that opens/closes one `sandbox` or generic span with the original nine fields. New code (Phase 01+) must not add parameters to this helper.

No LangGraph in this section. No Langfuse SDK — OTLP only.

## Dependencies

Section 01 (`task_id`), Section 04 (sandbox runs to instrument).

## Atomic Implementation Tasks

1. Implement `TelemetrySink` Protocol and a `NoOpTelemetrySink` used in unit tests.
2. Implement `OtelTelemetrySink` with console exporter; OTLP URL from settings (empty = skip OTLP).
3. Implement `emit_node_event` as a wrapper over `TelemetrySink.span` with the original field list.
4. Wire `run_in_sandbox` to emit a `kind="sandbox"` span (`model_id`/tokens null-or-zero).
5. Bind `task_id` + `trace_id` on structlog for the duration of a sink span.
6. Unit test: in-memory OTel exporter (or `NoOp` plus a recording sink) asserts required attributes; a second test stubs the exporter to raise and asserts the sandbox command still completes.

## Manual Testing Procedure

1. Run Section 04 demo with tracing enabled.
2. If Langfuse (or any OTLP receiver) is running, confirm the span arrives with `task_id`. If not, console exporter is sufficient.
3. Grep logs: `task_id` matches the span attribute.

## Expected Demo

Console (or screenshot) of a sandbox span with §B.8.4 fields present (zeros/nulls allowed), plus a correlated log line.

## Acceptance Criteria

- [ ] `packages/common/telemetry.py` has no `opentelemetry` import (grep-verifiable).
- [ ] `tracing.py` is the only OTel SDK usage in Phase 00.
- [ ] Exporter failure does not fail sandbox execution (explicit test).
- [ ] `task_id` correlates across spans and logs.

## Risks

- **Risk:** Call sites import OTel directly. **Mitigation:** grep in CI (Phase 00 §06) for `opentelemetry` outside `tracing.py`.

## Future Improvements

- `record_metric` → Prometheus in Phase 15.
- GenAI semantic convention aliases (`gen_ai.*`) as additional attributes once LLM spans exist (Phase 02).
- 90-day retention — ops concern after real volume (Phase 05+).

## Research Opportunities

None.
