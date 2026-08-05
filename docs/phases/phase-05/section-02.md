# Section 02 — ApprovalGate & Validator Templates

## Objective

Implement the two reusable agent templates from §E.1 — `ApprovalGate` and `Validator` — as config-parametrized graph node factories, replacing what would otherwise become N bespoke classes across the remaining 12 phases.

## Why It Exists

This is the architectural decision that keeps agent sprawl under control for the rest of the roadmap (§E.2: "Bespoke agents for patterns that are the same design is unjustified complexity"). Every future checkpoint (`scope`, `design`, `security`, `release`, `pr`, `deployment`) and every future validation step (`requirements`, `design`, `implementation`, `qa`) is a config instance of one of these two templates, never a new class.

## Expected Architecture

`packages/agents/templates/approval_gate.py`'s `ApprovalGate` is instantiated with `{checkpoint, evidence_bundle_spec, applies_when, decision_options, timeout_minutes}` (§E.1) and produces a graph node that: builds the evidence bundle, calls `interrupt()` (Phase 01's proven mechanism) with the bundle and options, and on resume, records an `ApprovalRecord` (Phase 00's `Task` model) and routes based on the decision. Critically, **timeout is Fail-Closed**: if `timeout_minutes` elapses with no response, the gate escalates (holds, notifies), it never auto-approves. `packages/agents/templates/validator.py`'s `Validator` is instantiated with `{phase, rule_set, independent_of, on_failure}` and produces a node that runs the named `rule_set` (a pluggable check function/config) against the producing agent's output, structurally enforcing `independent_of` (the validator's code path must not share mutable state or a cached model response with the producing agent — verified by construction, e.g., separate model call, separate function scope).

## Dependencies

Section 01 (`BaseAgent`/MASC), Phase 01 (`interrupt()`/`Command(resume=...)`).

## Atomic Implementation Tasks

1. Implement the `ApprovalGate` config schema and node-factory function (`build_approval_gate_node(config) -> node_fn`).
2. Implement evidence bundle assembly as a pluggable `evidence_bundle_spec` — at this phase, a minimal bundle (task summary, current phase artifact, confidence breakdown) since QA/diff evidence doesn't exist until later phases; the spec mechanism itself must be generic enough to grow.
3. Implement timeout handling: since `interrupt()` itself is process-paused (not wall-clock-timed by LangGraph natively), implement timeout via a scheduled check (e.g., an ARQ job checking `hitl_log.timeout_at` per §R's schema) that, on expiry, escalates rather than auto-resuming with an approval.
4. Implement the `Validator` config schema and node-factory function, with `rule_set` as a pluggable callable registry (`consistency-checker` for requirements is the first real rule set, built in Section 05).
5. Implement `on_failure` routing (`feedback_loop | hitl | suspend`) — at this phase, only `feedback_loop` (back to the producing agent) and `hitl` are reachable; `suspend` is exercised once the global rollback-count guard exists (Phase 10's Feedback Loop Registry, §F.5).
6. Unit tests: an `ApprovalGate` instance correctly pauses, and correctly escalates (does not auto-approve) on simulated timeout; a `Validator` instance correctly routes to `feedback_loop` on failure and passes through on success; confirm `independent_of` is structurally true (e.g., the validator's model call, if any, uses a fresh context, not a cached reference to the producing agent's response).

## Manual Testing Procedure

1. Instantiate an `ApprovalGate`(scope) against a live task, trigger it, and manually approve via the resume script (Phase 01 §03's pattern).
2. Instantiate the same gate again, and let it sit past a (short, test-configured) timeout — confirm it escalates rather than silently approving.
3. Instantiate a `Validator` with a deliberately failing rule set and confirm the `feedback_loop` routing fires with a structured `ValidationFlag`.

## Expected Demo

Two terminal recordings: one showing a normal approve flow through `ApprovalGate`(scope); one showing a timeout correctly escalating instead of auto-approving — the second is the more important proof, since it's the one that could silently violate Principle 4/8 if built wrong.

## Acceptance Criteria

- [ ] `ApprovalGate` correctly pauses via `interrupt()`, records the `ApprovalRecord`, and routes on resume.
- [ ] `ApprovalGate` timeout behavior is Fail-Closed: verified by an explicit test that a timed-out gate never resolves to "approved."
- [ ] `Validator` correctly runs a pluggable rule set and routes per `on_failure`.
- [ ] Both templates are demonstrably reusable — proven by configuring at least two distinct `ApprovalGate` checkpoints and at least one `Validator` phase from the same underlying classes, with zero new subclasses.

## Risks

- **Risk:** The temptation to special-case "just this one checkpoint needs slightly different behavior" into a new bespoke class. **Mitigation:** treat any such need as a signal to extend the template's config schema (a new optional field), not to fork a new class — consistent with `development_strategy.md` §6's stated seam-protection rule.

## Future Improvements

- Additional `rule_set` implementations for design/implementation/QA phases — Phase 06/07.
- Full evidence bundle richness (diffs, QA summaries, precedent tasks) — grows incrementally through Phase 08/13.

## Research Opportunities

None — this is the template pattern the blueprint explicitly designed to avoid ad hoc research/variation.
