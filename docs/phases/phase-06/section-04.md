# Section 04 — Implementation Manager & Task Decomposition

## Objective

Implement the Implementation Manager (§E.8): decomposes an approved `ArchitectureDoc` into a `TaskDecomposition` (§B.2) — a set of module-scoped sub-tasks with dependency-aware execution ordering — using `RepositoryIntelligence`'s `get_dependencies`/`get_dependents` to detect circular dependencies and resolve overlapping ownership before dispatch.

## Why It Exists

This is the coordination layer that makes Section 05's parallel fan-out safe: deciding *what* can run in parallel (independent modules) versus *what* must run sequentially (dependent modules) is a real graph-analysis problem, not a guess. Getting this wrong either serializes everything unnecessarily (slow) or parallelizes things that conflict (Section 06's problem to catch, but better avoided at the source here).

## Expected Architecture

`packages/agents/implementation/implementation_manager.py`'s `ImplementationManager(BaseAgent)` runs at High-capability tier, takes the approved `ArchitectureDoc` + `RequirementsSpec`, and produces `TaskDecomposition` (`tasks: [{id, description, module, dependencies}]`, `execution_order: [[parallel_group],...]`, `ownership_map: {module_path: sub_agent_id}`). It calls `get_dependencies`/`get_dependents` (Phase 03) per affected module to build the real dependency ordering, and explicitly checks for circular dependencies (fail loudly — a circular dependency between proposed sub-tasks is a design decomposition bug) and overlapping ownership (two sub-tasks claiming the same file/module — resolved by merging into one sub-task before dispatch, not discovered later at fan-in).

**Pre-dispatch overlap check (§D.4.2):** immediately before calling `Send()` for any parallel group, the Manager runs one deterministic, zero-LLM validation: compare `ownership_map`, planned file sets (via RI file index), and dependency graph for sub-tasks in the same parallel group. If obvious file-level overlap is detected, adjust decomposition (merge sub-tasks or move one to a later sequential group) before dispatch. This is an optimization only — Phase 06 §06's Fan-in Coordinator remains the final authority for overlap and conflict detection after workers execute.

This section also introduces the minimal `BlackboardService` (`packages/orchestration/blackboard.py`, §D.9.4: `store`/`retrieve`/`exists`, Postgres-backed) — it must exist before Section 05's CodeGen sub-agents produce their first real diffs, since diffs and any `WorkerCoordinationPacket.artifact_refs`/`ClarificationEscalation.evidence_refs` are stored here rather than inlined into `SDLCState`. Pointers use format `{task_id}/{kind}/{uuid}` (§D.4.3). Fail-Closed behavior on store/retrieve failure is defined in §D.9.4. Phase 08 enriches this same service, it does not originate it.

**Manager Authority (§D.9.5):** the Implementation Manager is the *only* node in this phase authorized to call `Send` (dispatch), redistribute a sub-task between workers, or trigger a replan. CodeGen sub-agents (Section 05) never do any of these — a blocked sub-agent raises a `ClarificationEscalation` and stops; only this Manager redispatches. Keep this boundary explicit in the node wiring, not just in agent prompts.

## Dependencies

Section 03 (approved, validated `ArchitectureDoc`), Phase 03 (`RepositoryIntelligence` graph queries).

## Atomic Implementation Tasks

1. Implement `TaskDecomposition` schema per §B.2 as the Implementation Manager's output.
2. Implement the decomposition prompt/logic: given the architecture's `component_boundaries`, propose one sub-task per independently-implementable unit.
3. Implement dependency-graph cross-checking: for each proposed sub-task, call `get_dependencies`/`get_dependents` on its target module(s) and validate the proposed `execution_order` is consistent with real, actual code dependencies (not just the LLM's guess) — this is the section's core "ground the plan in reality" step, same philosophy as Section 01's Repo Architecture Analyst.
4. Implement circular-dependency detection (topological sort failure → reject and retry decomposition, or escalate if retries exhausted) and overlapping-ownership resolution (merge sub-tasks claiming the same file).
5. Implement the pre-dispatch overlap check (§D.4.2): before `Send()`, compare planned file ownership across sub-tasks in each parallel group using RI — adjust decomposition if obvious overlap detected; otherwise proceed.
6. Implement the real `implementation` graph node's entry logic (decomposition step only — fan-out is Section 05).
7. Implement `BlackboardService` (`store`/`retrieve`/`exists`, §D.9.4) as a thin Postgres JSONB-backed service; wire it in as a dependency the Implementation Manager and (Section 05's) CodeGen sub-agents both receive, not a global singleton reached for implicitly.
8. Implement `ReplanContext` (§B.2) assembly: given a `task_id`, aggregate prior `TaskDecomposition`, `worker_coordination_packets`, `clarification_escalations`, and `feedback_reports` from `SDLCState` into the structured replan input — this is exercised for real starting Section 07, but the assembly function belongs here alongside the Manager it feeds.
9. Integration test: the demo feature request (touching 2–3 interdependent files) produces a `TaskDecomposition` whose `execution_order` correctly serializes the dependent pair and parallelizes the independent one.
10. Integration test: deliberately craft a decomposition with two sub-tasks in the same parallel group claiming overlapping files and confirm the pre-dispatch check merges or reschedules them before any `Send()` call.

## Manual Testing Procedure

1. Run the demo feature through Implementation Manager; print the full `TaskDecomposition`.
2. Manually verify the `execution_order` against the demo repo's actual dependency structure (cross-check with Phase 03's `get_dependencies` output directly).
3. Deliberately craft a design that would produce circular sub-task dependencies and confirm the Implementation Manager detects and rejects/retries rather than producing an invalid plan.

## Expected Demo

Terminal output of `TaskDecomposition` for the demo feature, with an explicit call-out of which sub-tasks are grouped for parallel execution and which are sequential due to real dependency edges — cross-referenced against a printed `get_dependencies` call proving the ordering is grounded, not guessed.

## Acceptance Criteria

- [ ] `TaskDecomposition.execution_order` is verified consistent with real dependency-graph data for the demo feature.
- [ ] Circular dependencies among proposed sub-tasks are detected and never silently passed through to dispatch.
- [ ] Overlapping file/module ownership across sub-tasks is resolved (merged) before dispatch, not left for fan-in to discover.
- [ ] Pre-dispatch overlap check (§D.4.2) prevents obvious same-group file overlap from reaching `Send()` — verified by a dedicated test distinct from the fan-in overlap test in Section 06.

## Risks

- **Risk:** Decomposition granularity is a real judgment call — too coarse loses parallelism benefit, too fine creates excessive coordination overhead and increases the chance of subtle cross-sub-task interface mismatches. **Mitigation:** no hard rule is prescribed; treat this as something to observe and tune per §E.2's principle ("sub-agents only where tool or context requirements genuinely differ" — apply the same discipline to task granularity).

## Future Improvements

- Dependency-fan-out-aware `max_parallel_impl_agents` capping by repo scale (§F.2) — Phase 10, once `WorkflowContext` is fully wired.

## Research Opportunities

Once several real decompositions exist, examine whether LLM-proposed sub-task boundaries tend to align with or diverge from the real dependency graph — informs whether the Implementation Manager should be given the dependency graph *before* proposing decomposition (current design) vs. proposing first and reconciling after (alternative worth comparing).
