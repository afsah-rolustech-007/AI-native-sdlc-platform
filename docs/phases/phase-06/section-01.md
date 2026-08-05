# Section 01 — Design Manager & Repo Architecture Analyst

## Objective

Implement the Design Manager (coordinates design, allocates heavy reasoning budget) and Repo Architecture Analyst (grounds the design in actual repo structure) per §E.8, producing a real `ArchitectureDoc` (§B.2) from an approved `RequirementsSpec`.

## Why It Exists

This is the first agent whose output genuinely determines code quality downstream — a wrong design assumption here is expensive to unwind later (per §D.3's rollback table, a design-phase requirement gap costs a full rollback to Requirements with HITL). Grounding it in real repo structure (not the model's imagination of the codebase) is what the Repo Architecture Analyst specifically exists to prevent.

## Expected Architecture

`packages/agents/design/design_manager.py`'s `DesignManager(BaseAgent)` runs at High-capability tier (§E.8), takes the `RequirementsSpec` + Phase Handoff Packet (raw form at this phase — full budget-capped packets are Phase 12) and produces `ArchitectureDoc` (`component_boundaries`, `api_contracts`, `database_design`, `security_design` stub, `deployment_strategy`, `adr_ids`). `packages/agents/design/repo_architecture_analyst.py`'s `RepoArchitectureAnalyst(BaseAgent)` runs at Fast tier, queries `RepositoryIntelligence` (Phase 03) for structural context scoped 2 hops from affected modules (per §E.8's table), and attaches an "architecture-fit analysis" the Design Manager consumes before finalizing.

## Dependencies

Phase 05 (approved requirements, agent scaffolding), Phase 03 (`RepositoryIntelligence`).

## Atomic Implementation Tasks

1. Implement `ArchitectureDoc` schema per §B.2 as the Design Manager's output schema (§M.1 protocol).
2. Implement `RepoArchitectureAnalyst`: given the requirements' affected modules (a field to derive/infer at this phase — document the derivation, e.g., from explicit scope hints in requirements or a semantic search against the spec), call `get_dependencies`/`get_dependents`/`get_callers` (2-hop) and `search_concepts` to assemble a structural context bundle.
3. Implement `DesignManager.build_context()` combining: architecture summary (L0, always), the Repo Architecture Analyst's fit-analysis, and the requirements handoff.
4. Implement `DesignManager.run()` producing the full `ArchitectureDoc`, including at least one real ADR (`design_decisions` table, §R) for a non-trivial design choice.
5. Wire the real `design` graph node (replacing Phase 01's stub) to run Repo Architecture Analyst → Design Manager in sequence.
6. Integration test: run the demo feature request (Phase 06 README) through this node, confirm `ArchitectureDoc` correctly references real files/modules from the demo repo (not hallucinated paths) — verified by cross-checking against `RepositoryIntelligence`.

## Manual Testing Procedure

1. Run the demo feature request through Design; print the full `ArchitectureDoc`.
2. Manually verify every file/module path referenced in the design actually exists in the demo repo (catches hallucinated structure — a real risk worth explicitly checking, not assuming away).
3. Query `design_decisions` and confirm at least one ADR was recorded.

## Expected Demo

Terminal output of a full `ArchitectureDoc` for the demo feature, annotated with which parts came from the Repo Architecture Analyst's grounding vs. the Design Manager's synthesis — plus the recorded ADR.

## Acceptance Criteria

- [ ] `ArchitectureDoc` is fully populated and every referenced file/module path is verified real (not hallucinated) against the demo repo.
- [ ] At least one ADR is recorded to `design_decisions` per design session.
- [ ] The real `design` node replaces Phase 01's stub in the compiled graph.

## Risks

- **Risk:** LLM hallucination of file/module structure despite grounding — the Repo Architecture Analyst reduces but does not eliminate this risk. **Mitigation:** the manual cross-check in this section's test procedure is the first line of defense; `Validator`(design) (Section 03) is the systematic, automated defense that must not be skipped.

## Future Improvements

- Aider-style PageRank repo map injection (Level 0.5 context) — Phase 12; at this phase, the Repo Architecture Analyst's 2-hop structural query is the only grounding mechanism.

## Research Opportunities

Track how often the Repo Architecture Analyst's fit-analysis actually changes the Design Manager's output vs. being ignored — an early signal (once Phase 15 exists) of whether this split agent is earning its complexity per §E.2's "sub-agents only where genuinely different" principle.
