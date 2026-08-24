# Section 04 — Implementation Manager, Topology Selector & Blackboard

## Objective

Implement the Implementation Manager (§E.8): decomposes an approved `ArchitectureDoc` into a `TaskDecomposition` (§B.2) — WHAT + `declared_dependencies` — then invokes the deterministic Topology Selector (`plan_execution_waves()`, §D.10.3) to produce the active `ExecutionPlan` and `TopologyDecisionRecord`. Also introduce the minimal `BlackboardService` (§D.9.4).

## Why It Exists

The Manager must not silently be the scheduler, and must not spend extra LLM rounds pretending to be RI. **One High-capability structured-output call** produces `TaskDecomposition` (WHAT: subtasks, `target_files`, `declared_dependencies`, `model_tier_hint`). **Zero tools on that call.** Then the same graph node runs `plan_execution_waves()` in Python (WHEN). TP-01…TP-08 are YAML-driven deterministic policy, not model decisions (§D.10.3.1, §D.10.11).

## Expected Architecture

`ImplementationManager(BaseAgent)` (High-capability) produces `TaskDecomposition` in **one** structured-output invocation. Prompt context is injected (ArchitectureDoc, Design→Implementation handoff, L0 summary). **Do not** attach `get_dependencies` / `get_callers` as Manager tools on this call — that creates a hidden ReAct tax.

Forbidden Manager outputs: `topology_class`, waves, `max_wave_width`, `confidence_score`, `risk_tier`. Complexity, if present, may only set `model_tier_hint` (Fast vs High per subtask).

**Topology Selector** — `plan_execution_waves(decomposition, sdg, profile, ctx, task)` in the **same node** after the LLM returns:

1. Seed / RI-verify SDG (budget §D.10.7); cycle → replan path, never dispatch.
2. Apply TP hard gates then soft min-caps (§D.10.3) using exact inputs:
   - `task.risk_tier`, `task.confidence_score`
   - `ctx.repo_scale`, `ctx.max_parallel_impl_agents`
   - `profile.max_parallelism`
   - `sdg.ri_available`
3. Levelize; width-cap split; derive `topology_class` per §D.10.3 exact rules.
4. Write `SDLCState.execution_plan`, `plan_version`, `topology_decisions`.

**Pre-dispatch overlap check (§D.4.2)** is superseded by the Selector — do not implement both.

**Manager authority (§D.9.5):** coordination only (decompose / replan / reassign). Mechanical `Send` is Wave Scheduler (Section 05).

**BlackboardService** — `store`/`retrieve`/`exists`, Postgres JSONB; pointer format `{task_id}/{kind}/{uuid}`.

## Dependencies

Section 03 (approved `ArchitectureDoc`), Phase 03 (RI). Until Phase 10: `WorkflowProfile.most_conservative()` and a local `WorkflowContext` subset with `repo_scale` from file-count heuristic (default `medium` if unknown — never default `small`).

## Atomic Implementation Tasks

1. `TaskDecomposition` schema per §B.2 — **no** `execution_order` field.
2. Decomposition prompt: one sub-task per unit + explicit `declared_dependencies`.
3. `plan_execution_waves()` pure function + injected RI adapter — unit tests for TP-01…TP-08, topology_class derivation, cycle detection, RI-unavailable.
4. RI verification + query budget cap (§D.10.7).
5. `BlackboardService` + `ReplanContext` assembly including `previous_plan`, `completed_wave_indices`, `discovered_edges`.
6. Integration test: hybrid soft-delete Users example from §D.10.3.
7. Integration test: CRITICAL → all width 1 (TP-03); RI down → TP-01 sequential.

## Acceptance Criteria

- [ ] Active schedule comes from `ExecutionPlan`. Manager output has no `execution_order`.
- [ ] TP hard/soft semantics match §D.10.3; CRITICAL is width 1; TP-02 uses **0.70** (not §B.4's 0.75).
- [ ] `profile.execution_order == "sequential"` → width 1; field is not `topology_class`.
- [ ] `TopologyDecisionRecord.policy_rules_fired` / `width_cap_source` populated.
- [ ] Cycles never dispatched.
- [ ] Trace of happy-path decompose shows **exactly one** High-capability `llm_call` span before Wave Scheduler; Topology Selector / Fan-in / Scheduler spans have no `model_id`.
- [ ] Manager decompose call has **zero** RI tool_call children.
- [ ] TP evaluation loads `configs/topology_policy.yaml`; unit tests swap YAML and get different `max_wave_width` without any model.

## Risks

- Decomposition granularity vs coordination overhead — observe; tune with Phase 15 topology KPIs.
- `repo_scale` heuristic before Phase 10 — document; default medium.

## Future Improvements

- Full `WorkflowContext` from Phase 10.
- Tier-C historical topology calibration (Phase 15+).
