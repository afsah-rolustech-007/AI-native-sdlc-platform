# Section 05 — OTel Observability Backbone

## Objective

Stand up the OpenTelemetry tracing pipeline described in §B.8: every graph node (once graphs exist, Phase 01+) will emit a structured trace event `{task_id, node_id, agent_id, phase, model_id, input_tokens, output_tokens, cost_usd, latency_ms, validation_result}`. This section builds and proves the pipeline itself using the sandbox runs from Section 04 as the first real trace-emitting events.

## Why It Exists

Debuggability across 17 phases of increasingly autonomous agent behavior depends entirely on this existing from day one. Without it, Phase 06's "why did the CodeGen sub-agent fail three times" question has no evidence trail. Retrofitting tracing after agents exist means re-instrumenting every agent node — expensive. This section makes emitting a trace event as easy as calling one function, so no future agent skips it out of friction.

## Expected Architecture

`packages/common/tracing.py` configures the OTel SDK with a console exporter (dev) and an OTLP exporter (for Langfuse, if run per `techstack.md`). A single `emit_node_event(**fields)` helper wraps span creation so call sites are one line. Structured logging (`structlog`) is configured to route through the same pipeline so log lines and trace spans correlate by `task_id`.

## Dependencies

Section 01 (task_id to correlate events), Section 04 (sandbox runs are the first thing worth tracing).

## Atomic Implementation Tasks

1. Configure the OTel SDK: tracer provider, console span exporter for local dev, OTLP exporter pointed at a local Langfuse/collector instance if running.
2. Implement `emit_node_event(task_id, node_id, agent_id, phase, model_id, input_tokens, output_tokens, cost_usd, latency_ms, validation_result)` as a thin wrapper creating a span with these as attributes.
3. Wire `emit_node_event` into `run_in_sandbox` (Section 04) so every sandbox execution automatically emits a trace event (with `model_id=None`, `input_tokens=0` etc. since no LLM is involved yet — proving the schema tolerates the agent-less case cleanly).
4. Configure `structlog` to bind `task_id` and `trace_id` into every log line automatically within a task's execution context (e.g., via `contextvars`).
5. Add a retention note/config comment: full trace retention target is 90 days (§B.8) — not enforced in code at this phase (no data volume yet), but the exporter config should make setting a retention policy trivial later.
6. Unit/integration test: run a sandboxed command, capture the emitted span via an in-memory OTel exporter in the test, assert all required attributes are present and correctly typed.

## Manual Testing Procedure

1. Run the Section 04 demo commands with tracing enabled.
2. If Langfuse is running locally, open its UI and confirm the trace event appears with correct `task_id` correlation.
3. If not running Langfuse, confirm the console exporter prints a well-formed span with all required fields.
4. Grep application logs for a `task_id` and confirm log lines and trace span share the same identifier.

## Expected Demo

Screenshot (or console output) of a trace event for a sandbox run, showing every required field from §B.8's schema populated (with `None`/`0` placeholders where not yet applicable), alongside a correlated log line.

## Acceptance Criteria

- [ ] Every field in §B.8's event schema is present on every emitted event, even when zero/null for non-LLM events.
- [ ] `task_id` correlates across trace spans and structured log lines for the same execution.
- [ ] Tracing failure (e.g., exporter unreachable) does not crash or block the underlying operation — tracing is best-effort/non-blocking, verified with a test that disables the exporter and confirms the sandboxed command still completes.

## Risks

- **Risk:** Treating tracing as load-bearing for control flow (e.g., accidentally making a code path depend on a trace call succeeding) would violate the "tracing must not block execution" principle. **Mitigation:** explicit test in Section 05 (see above) proving trace emission failures are swallowed/logged, not propagated.

## Future Improvements

- Prometheus/Grafana dashboards on top of these events — Phase 15.
- Formal 90-day retention + indefinite episodic summarization — becomes relevant once real data volume exists (Phase 05+).

## Research Opportunities

None at this stage — this is infrastructure, not a research question.
