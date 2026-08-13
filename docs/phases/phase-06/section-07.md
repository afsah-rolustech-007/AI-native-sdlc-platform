# Section 07 — Validator(implementation) & Feedback Agent

## Objective

Implement `Validator`(implementation) — a tool-only, zero-LLM static validation pass (ruff, mypy, Semgrep) independent of CodeGen — and the Feedback Agent (§E.5), the named response to N consecutive failures on the same module, closing out Phase 06's full implementation agent roster and its feedback loops (`FL-04`).

## Why It Exists

`Validator`(implementation) is the cheapest, fastest, most deterministic check in the whole roster (§E.8: "Model Tier: None (tools only)") and should catch the majority of mechanical issues before anything more expensive (Integration Validator, QA phase) runs. The Feedback Agent exists because, per the blueprint's own gap analysis (§0.2 #1), "neither prior document adequately specified what happens after N consecutive failures" — a blind retry wastes budget and rarely fixes a systemic misunderstanding; root-cause synthesis across failure history is what actually helps.

## Expected Architecture

`Validator`(implementation) is a `Validator` template instance with `rule_set="static-analysis"`, running ruff/mypy/Semgrep (Phase 00's sandbox, no LLM call) against each CodeGen sub-agent's diff, independent of the CodeGen agent itself (separate process invocation). On failure, `FL-04` routes back to the specific CodeGen sub-agent with a structured `FeedbackReport` (§D.8), max 3× per §F.5. On the 3rd consecutive failure for the same module (tracked via `Task.budget.max_retries_per_node`), the Feedback Agent (§E.5, High-capability tier) is invoked: given a `ReplanContext` (§B.2, assembled by Section 04's helper) — the module's full `FeedbackReport` history, its `WorkerCoordinationPacket`s, and episodic memory of similar past failures (stubbed at this phase — no real episodic corpus exists yet; document this as a known limitation until enough task history accumulates) — it synthesizes a root-cause diagnosis and produces a *revised* `TaskDecomposition` entry — a different approach, not a repeat of the same instructions. If the Feedback Agent's revised approach also fails, escalate to human (Fail-Closed, per §E.5's explicit rule — never loop indefinitely).

**`FeedbackReport` vs. `ClarificationEscalation` (§D.8's distinction, concretely exercised here for the first time):** a `FeedbackReport` only ever exists *after* `Validator`(implementation) rejects a *completed* diff — it's a post-hoc correction signal. A `ClarificationEscalation` (Section 05/06) exists *before* a worker completes at all — it's an "I cannot safely finish" signal. The Feedback Agent only ever consumes the former; it never sees an unresolved `ClarificationEscalation` directly (those are resolved by the Manager at fan-in, per Section 06, before a module could even reach this section's 3-failure counter for reasons related to that escalation).

## Dependencies

Section 05 (CodeGen diffs to validate), Section 06 (fan-in must complete before or alongside this, depending on final node ordering — decide and document whether static validation runs per-sub-task before fan-in or on the merged result after; the blueprint's agent table implies per-diff, independent of CodeGen, suggesting pre-fan-in is more consistent with "catch issues early, cheaply").

## Atomic Implementation Tasks

1. Implement `Validator`(implementation)'s `static-analysis` rule set: ruff + mypy + Semgrep run against a diff inside the sandbox, aggregated into a pass/fail + findings list.
2. Implement `FL-04` routing: on failure, structured `FeedbackReport` (§D.8: `loop_id`, `failed_agent`, `failure_type`, `validator_findings`, `specific_gaps`, `suggested_approach`, `attempt_number`) sent back to the same CodeGen sub-agent instance, incrementing `attempt_number`.
3. Implement failure-count tracking per module (not per generic retry counter — must be scoped to "same module," per §E.5's trigger condition).
4. Implement `FeedbackAgent(BaseAgent)`, High-capability tier: input is the `ReplanContext` (Section 04) for the module — all `FeedbackReport`s so far plus relevant `WorkerCoordinationPacket`s — plus a stubbed episodic-memory lookup (returns empty/neutral until real data exists, same documented-limitation pattern as Phase 05 §05's `precedent_strength` placeholder); output is a revised `TaskDecomposition` entry with explicit constraints and a different suggested approach.
5. Implement the "Feedback Agent's revised approach also fails → escalate to human" terminal condition — a real `interrupt()`/`ApprovalGate`-style escalation (reuse Phase 05 §02's template rather than inventing new escalation UI).
6. Integration test: deliberately craft a CodeGen scenario that fails static analysis 3 times in a row (e.g., a sub-task description that reliably produces a lint violation), confirm `FL-04` fires each time with a real, specific `FeedbackReport`, confirm the Feedback Agent activates on the 3rd failure and produces a genuinely different revised approach (not a copy of the original), and confirm a 4th failure (if forced) escalates to human rather than looping again.



## Manual Testing Procedure

1. Run the demo feature's normal path and confirm `Validator`(implementation) passes cleanly with zero LLM cost (verify via trace: no `model_id` populated for this validator's events).
2. Force a failure scenario and manually inspect the `FeedbackReport`'s `specific_gaps` — confirm it's genuinely specific ("unused import on line 12," not "fix your code").
3. Force 3 consecutive failures and confirm the Feedback Agent's revised approach is visibly different in substance from the original task instructions, not a rephrasing.



## Expected Demo

Terminal walkthrough of a forced 3-failure sequence: each `FeedbackReport` printed, then the Feedback Agent's root-cause diagnosis and revised approach, then (if a 4th failure is forced) the human-escalation interrupt firing — this is the demo that proves §E.5's design intent (root-cause synthesis, not blind retry) is real, not just documented.

## Acceptance Criteria

- [ ] `Validator`(implementation) runs entirely tool-based, with zero LLM cost, verified via trace inspection.
- [ ] `FL-04`'s `FeedbackReport`s contain specific, actionable findings (not generic "try again" text) — spot-checked manually.
- [ ] Feedback Agent triggers correctly on the Nth consecutive same-module failure (N = `max_retries_per_node`) and produces a demonstrably different revised approach.
- [ ] A failing Feedback Agent revision escalates to a human, never loops indefinitely — verified by an explicit test forcing this path.



## Risks

- **Risk:** Without real episodic memory, the Feedback Agent's "learn from similar past failures" capability is currently just "reason harder about this one failure history" — a real but understated capability gap versus the blueprint's full vision. **Mitigation:** documented explicitly as provisional; Phase 06 itself is what starts generating the episodic data (`regression_history`, §R) that makes this fully real by the time enough tasks have run.



## Future Improvements

- Real episodic-memory-backed failure pattern matching for the Feedback Agent — becomes possible once `regression_history` (§R) has meaningful volume (Phase 07+ populates it via QA's regression test generation, §K.4).



## Research Opportunities

This is a strong candidate for early qualitative research: once a handful of real Feedback Agent interventions exist, review them by hand — did the revised approach actually differ meaningfully, and did it resolve the failure? This is cheap to do now and directly informs whether the agent's prompt needs work before investing further.