# Section 01 — Agent Base Class & MASC Middleware

## Objective

Implement `BaseAgent` — the common scaffolding every agent inherits (model routing, retry policy, OTel tracing, MASC validation hookup) — and the MASC Engine's first two checks (schema validation, confidence gating) as post-node middleware per §E.6. Semantic drift (Check 3) is stubbed until Phase 06 introduces the first genuinely high-stakes phase output (design) worth checking for drift against.

## Why It Exists

Every one of the ~25 named agents across §E.8's roster shares the same cross-cutting concerns: call a model via the router, validate the output before it enters state, trace the call, retry on transient failure. Building this once, correctly, before the first real agent (Section 03) is written, is what prevents 20+ phases of agents from each reinventing (and inconsistently getting wrong) this scaffolding.

## Expected Architecture

`packages/agents/base.py`'s `BaseAgent` provides: a `run(state: SDLCState) -> SDLCState` template method that (1) assembles context (minimally at this phase — full progressive/budgeted context assembly is Phase 12), (2) opens an `kind="agent"` span on `TelemetrySink`, (3) calls `ModelRouter.select()` (Phase 02) for the appropriate `(phase, operation)`, (4) invokes the model via `ModelAdapter` (child `llm_call` spans from Phase 02 wrapper), (5) records `tool_call` spans around each tool invocation, (6) passes the raw output through `MASCEngine.validate()` inside a `validation` span, (7) on failure, raises a structured error the graph's retry policy handles (`attempt_number` on the next agent span), (8) on success, writes validated output to `SDLCState` and ends the agent span. `packages/orchestration/masc.py` implements `MASCEngine` per §E.6, with Check 1 (schema validation against the agent's declared Pydantic output schema) and Check 2 (confidence threshold from §B.4's phase floors) fully implemented; Check 3 (semantic drift) implemented as an interface method that returns "not checked" until Phase 06.

## Dependencies

Phase 02 (`ModelRouter`, `ModelAdapter`), Phase 00 (tracing, budget).

## Atomic Implementation Tasks

1. Implement `BaseAgent` as an abstract base class with the `run()` template method and abstract `build_context()`/`output_schema` hooks each concrete agent must supply.
2. Implement `MASCEngine.validate(output, agent_id, phase, state)` per §E.6's exact structure: Check 1 (Pydantic schema validation, zero tokens), Check 2 (confidence threshold lookup from §B.4's `CONFIDENCE_THRESHOLDS`, zero tokens), Check 3 stub.
3. Implement Fail-Closed behavior for MASC itself: if `validate()` raises internally (bug in a check, unexpected input shape), treat as `severity="error"`, route to human — per §E.6's own comment ("Fail-Closed: if MASC itself errors → treat as severity='error', route to human"). Unit-test this explicitly, following the same pattern established in Phase 00 §03 and Phase 04 §04.
4. Wire per-node retry policy using `Task.budget.max_retries_per_node` (Phase 00's `Task` model) — exponential backoff, per §D.5.
5. Wire `BaseAgent.run()` to `TelemetrySink` spans as specified in Expected Architecture — not `emit_node_event` with a growing kwargs list.
6. Unit tests: a mock agent with a known-bad output schema is correctly rejected by MASC Check 1; a mock agent whose declared confidence is below the phase floor is correctly rejected by Check 2; a MASC internal exception correctly resolves to "error, route to human," not silently passing.

## Manual Testing Procedure

1. Implement a trivial test agent (e.g., one that echoes input with a fixed confidence value) using `BaseAgent`.
2. Run it with a confidence value above and below the phase floor, confirming MASC Check 2 behaves correctly in both cases.
3. Deliberately have the test agent return a schema-violating output and confirm Check 1 catches it before it reaches `SDLCState`.

## Expected Demo

Terminal output of the trivial test agent run three times: (1) valid output, passes MASC, enters state; (2) low-confidence output, rejected with a `ValidationFlag`; (3) schema-violating output, rejected with a different `ValidationFlag` — showing all three MASC outcomes concretely.

## Acceptance Criteria

- [ ] `BaseAgent` correctly integrates model routing, MASC validation, retry, and tracing for a trivial test agent.
- [ ] MASC Checks 1 and 2 are fully functional and independently unit-tested, including their own Fail-Closed behavior.
- [ ] Every real agent output flowing through `BaseAgent.run()` produces an AGENT span with child LLM and VALIDATION spans (`model_id`/tokens populated on LLM). `packages/agents/` has no `opentelemetry` import.

## Risks

- **Risk:** A shared base class risks becoming an overloaded "god class" as more phases add requirements to it. **Mitigation:** keep `BaseAgent` strictly to the five concerns listed above; phase-specific logic (e.g., Phase 06's parallel fan-out) belongs in subclasses or graph-level orchestration, not pushed into the shared base.

## Future Improvements

- Semantic drift check (MASC Check 3) — Phase 06, once Design phase output exists to check drift against.
- Reflection/self-critique pass integration (§M.3) — Phase 06, for Design Manager and Security Architect specifically.

## Research Opportunities

None yet — this section is scaffolding.
