# Section 01 — WorkflowContext Schema & Computed Fields

## Objective

Implement the full `WorkflowContext` schema per §F.2, including its `@computed_field` derived properties (`requires_full_design_phase`, `max_parallel_impl_agents`), and reconcile every partial/local `WorkflowContext`-subset built ad hoc during Phases 04–08 into this single, canonical schema.

## Why It Exists

Multiple prior sections (Phase 04 §01's question-predicate context, Phase 06 §02's security-sensitivity heuristic, Phase 06 §05's parallelism assumptions) each built a provisional, documented-as-temporary stand-in for this schema. This section is where those debts get paid down — replacing every heuristic with the real, complete field set the blueprint specifies.

## Expected Architecture

`packages/workflow_engine/context.py` implements `WorkflowContext` exactly per §F.2: task properties, repository properties (including `repo_scale` — small/medium/large/enterprise, which directly informs Phase 11's scale work even though this phase doesn't yet operate at that scale), engineering constraints, and the two computed fields. A `build_workflow_context(task, repo_intel) -> WorkflowContext` factory function assembles a real instance from actual `Task` fields and real `RepositoryIntelligence` queries (e.g., `touches_shared_infra` derived from real module-ownership data, replacing Phase 06 §02's keyword heuristic).

## Dependencies

Phase 00 (`Task`), Phase 03 (`RepositoryIntelligence`, for repo-property derivation).

## Atomic Implementation Tasks

1. Implement the full `WorkflowContext` Pydantic model per §F.2's exact fields and computed properties.
2. Implement `build_workflow_context()`: derive `repo_architecture`/`repo_scale` from Phase 03's index stats (file counts, structure); derive `affected_module_count`/`dependency_fan_out`/`touches_shared_infra` from real `RepositoryIntelligence` queries against the task's affected modules; derive `has_database_changes`/`has_api_contract_changes`/`has_ui_changes` from the requirements/design artifacts already produced by Phases 05–06.
3. Replace Phase 04 §01's local `WorkflowContext`-subset with the real schema — update the Requirements Engine's `applies_if` predicates to consume the real fields.
4. Replace Phase 06 §02's security-sensitivity heuristic with the real `touches_shared_infra`/derived security classification.
5. Replace Phase 06 §05's implicit parallelism assumptions with `max_parallel_impl_agents` (§F.2's computed field, scale-capped per `repo_scale`).
6. Unit tests: each computed field produces correct output for representative input combinations; the reconciliation of Phase 04/06's provisional heuristics against the real schema is verified by re-running those phases' existing test scenarios and confirming equivalent or improved behavior (not a regression).

## Manual Testing Procedure

1. Run `build_workflow_context()` against the Phase 06 demo feature and print the full resulting context, including computed fields.
2. Manually verify `touches_shared_infra` and `repo_scale` are correctly derived from the actual demo repo, replacing the earlier heuristics.
3. Re-run Phase 04's three demo scenarios and Phase 06's security-triggering/non-triggering scenarios, confirming they still behave correctly (or better) under the real schema.

## Expected Demo

Terminal output of a fully populated `WorkflowContext` for the demo feature, with a side-by-side comparison against what Phase 06 §02's heuristic would have produced for the same input — showing the real schema is a strict improvement, not just a different guess.

## Acceptance Criteria

- [ ] `WorkflowContext` matches §F.2 exactly, including both computed fields.
- [ ] Every provisional context-subset/heuristic from Phases 04 and 06 is replaced by real derivation from this schema, with no regressions in those phases' existing tests.
- [ ] `build_workflow_context()` is grounded in real `RepositoryIntelligence` and `Task`/artifact data — no remaining placeholder/heuristic logic for the fields this section covers.

## Risks

- **Risk:** Reconciling multiple provisional implementations into one canonical schema risks subtly changing behavior in ways existing tests don't catch. **Mitigation:** the "re-run Phase 04/06's existing test scenarios" step in the manual testing procedure exists specifically to catch this — do not skip it.

## Future Improvements

- `repo_scale` classification refinement once Phase 11's federated sharding gives a more precise notion of scale than raw file count.

## Research Opportunities

None.
