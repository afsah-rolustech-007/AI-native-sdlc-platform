# Section 03 — Planning Manager & Intake Classification

## Objective

Implement the Planning Manager agent (§E.8, Intake & Planning) — the platform's first real, LLM-driven agent — which classifies a raw request into a `Task` (`work_type`, initial `risk_tier` estimate) and replaces Phase 01's stub `intake_node`.

## Why It Exists

Every downstream decision (which questions apply in Phase 04's engine, which workflow profile Phase 10 eventually selects) depends on an accurate initial classification. This is deliberately the *first* real agent because it's the lowest-stakes place to prove the full `BaseAgent` → `ModelAdapter` → MASC → `SDLCState` pipeline works, before anything expensive or safety-critical rides on it.

## Expected Architecture

`packages/agents/intake/planning_manager.py`'s `PlanningManager(BaseAgent)` takes a raw request string (plus any structured intake fields from a future UI form, Phase 09), calls the model (Fast tier per §E.8's table) with a classification prompt (structured output: `work_type`, initial `risk_tier` estimate, brief rationale), validates via MASC, and writes the classification onto the `Task` record and `SDLCState`. This becomes the real `intake` graph node, replacing Phase 01's stub.

## Dependencies

Section 01 (`BaseAgent`), Phase 00 (`Task` model, persistence).

## Atomic Implementation Tasks

1. Define the `PlanningManagerOutput` Pydantic schema (`work_type`, `risk_tier`, `rationale`, `confidence`) per §M.1's Output Schema Protocol — every agent's output schema from here forward lives in `agents/prompts/schemas/`.
2. Write the system prompt per §M.2's template structure (role, context injection order, constraints, output format) — this is the first real prompt in the codebase; treat it as a template other agents' prompts will follow structurally.
3. Implement `PlanningManager.build_context()` — at this phase, minimal: the raw request text plus `get_architecture_summary()` from Phase 03 (Level 0 context, always injected per §M.2).
4. Implement the node function replacing Phase 01's `intake_node`, calling `PlanningManager.run()` and updating `Task.type`/`Task.risk_tier` in Postgres.
5. Unit tests: mock model responses covering each `WorkType`; a response with a missing/invalid field is correctly caught by MASC Check 1; classification of a few realistic example requests (feature request, bug report, hotfix language) produces sensible `work_type` assignment — this is a *judgment* test, worth eyeballing rather than over-asserting exact values.
6. Integration test: run the real graph from Phase 01, with this node now real, through to the next (still-stub, until Section 04) node — confirming the wiring is correct end-to-end.

## Manual Testing Procedure

1. Submit 4–5 varied real-text requests (a clear feature ask, a bug report, a vague one-liner, a production-hotfix-sounding request) through the Planning Manager directly (not yet through the full graph).
2. Manually review each classification for reasonableness.
3. Run one request through the actual graph (Phase 01's compiled graph with this real node substituted) and confirm the `Task` record in Postgres reflects the classification.

## Expected Demo

Terminal output showing 4–5 real classifications side by side (request text → work_type, risk_tier, rationale) — the first visible proof that an LLM call is doing real, useful work inside this platform.

## Acceptance Criteria

- [ ] Planning Manager correctly classifies a representative set of varied requests (manually judged for reasonableness, not a numeric target at this phase — that comes with Phase 15's evaluation).
- [ ] Output is MASC-validated; a schema-invalid or below-floor-confidence classification is caught, not silently accepted.
- [ ] The real `intake` node is wired into the actual compiled graph from Phase 01, replacing the stub.
- [ ] Classification and cost/trace data are persisted and queryable in Postgres.

## Risks

- **Risk:** Fast-tier model misclassification on ambiguous requests, cascading into a wrong `risk_tier` that under-applies scrutiny later. **Mitigation:** this is exactly why `Validator`(requirements) (Section 05) and the fail-closed default profile (used until Phase 10) exist — misclassification here is caught downstream, not assumed impossible here.

## Future Improvements

- Fine-tuned intent/classification model — explicitly named in §E.3 as a candidate for fine-tuning once volume/data exists (Phase 15+); not justified now.

## Research Opportunities

Compare classification consistency across GLM-4.7 vs. GLM-4.7-Flash on the same request set — informs whether Fast tier (§E.8's table specifies Fast for Planning Manager) is actually sufficient, or whether this agent should be promoted to Balanced tier.
