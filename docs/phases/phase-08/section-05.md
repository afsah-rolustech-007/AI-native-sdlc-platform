# Section 05 — Release Manager, Rollback Sub-agent & Monitoring Manager

## Objective

Implement the Release Manager (coordinates deployment via existing CI/CD, never direct cloud API calls, §E.8), the Rollback Sub-agent (executes rollback on deployment failure or incident), and the Monitoring Manager (watches the bake-in period; on incident, spawns a **new** Task via lineage, never loops back into the original graph) — completing the full SDLC state machine from §D.3 for the first time, end to end.

## Why It Exists

This section closes the loop the entire platform exists to close: from an approved change to a live, monitored deployment, with automated safety nets (rollback on health failure) and a principled distinction (§0.2 #6) between "this deployment needs a fix" (new Task) and "resume the old task's context" (explicitly never done — a production incident deserves a fresh risk/confidence assessment, not stale assumptions from the original task).

## Expected Architecture

`packages/agents/release/release_manager.py`'s `ReleaseManager(BaseAgent)` (High-capability tier, §E.8) selects a deployment strategy (rolling/blue-green/canary — strategy *selection* logic can be simple/conservative at this phase, since the full canary-analysis thresholds are implied by the blueprint's comparative analysis (§0.1) but not spelled out as a dedicated section; a reasonable default here is documented explicitly as provisional) and triggers deployment **exclusively through an existing CI/CD pipeline adapter** — never a direct cloud provider API call (§B.6/§J.1, a hard architectural boundary). `ApprovalGate`(deployment) (Section 01) always gates this. `RollbackSubAgent` (Fast tier) executes a rollback plan via the same CI/CD adapter on health failure — immediate human escalation on rollback failure itself (§E.8: "Failure: IMMEDIATE human escalation"). `MonitoringManager` (Fast tier) watches post-deploy telemetry (OTel pipeline, Phase 00) for a configured bake-in window; on a detected incident, it creates a **new** `Task` with `lineage.root_incident_id` set, and does not resume or mutate the original task's `SDLCState` — the terminal, `monitoring`, node of the original task's graph completes normally regardless.

## Dependencies

Section 04 (merged PR to deploy), Phase 00 (OTel for post-deploy telemetry), Phase 01 (graph completion mechanics for the "spawn new Task" pattern).

## Atomic Implementation Tasks

1. Implement a CI/CD adapter interface (`trigger_deployment`, `check_health`, `trigger_rollback`) — implement a realistic local/simulated backend for this phase (e.g., a scripted deployment simulator with configurable health outcomes) since a real production CI/CD target is out of scope for a documentation-only planning exercise but the interface must be real and testable.
2. Implement `ReleaseManager`'s strategy selection (documented as a provisional/simple default) and deployment trigger via the adapter — explicitly never any direct cloud SDK import (grep-verifiable, same discipline as Phase 02's model-adapter check).
3. Implement `DeploymentRecord` (§B.2) population: strategy, target env, pipeline run id, health status.
4. Implement `RollbackSubAgent`'s rollback execution via the same adapter, and the immediate-human-escalation path on rollback failure.
5. Implement `MonitoringManager`'s bake-in watch loop and incident-detection logic (using simulated/configurable health signals for this phase's testing).
6. Implement new-Task spawning on incident detection: construct a new `Task` (§B.1) with `type=MAINTENANCE` or similar, `lineage={"root_incident_id": original_task_id}`, and route it through intake fresh — explicitly *not* reusing the original task's `SDLCState`.
7. Integration test: full end-to-end run from PR merge through deployment approval through simulated healthy bake-in to `TaskState.DONE`; separately, a run with a simulated post-deploy health failure, proving the Rollback Sub-agent fires and (if configured) a new incident Task is correctly spawned with correct lineage, while the original task's graph still reaches a clean terminal state.

## Manual Testing Procedure

1. Run the demo feature through to a successful simulated deployment and confirm `TaskState.DONE` with a fully populated `DeploymentRecord`.
2. Force a simulated post-deploy health degradation and confirm the Rollback Sub-agent triggers automatically.
3. Force a simulated incident during monitoring and confirm a new `Task` is created with correct `lineage.root_incident_id`, and that the original task's graph is unaffected (does not loop back, does not hang).

## Expected Demo

This section's demo *is* Phase 08's overall closing demo (see README): full PR-to-deployment-to-monitoring walkthrough including the forced rollback and forced-incident-spawns-new-Task paths — the first time the entire §D.3 state machine (intake through monitoring) runs for real, end to end.

## Acceptance Criteria

- [ ] Deployment is triggered exclusively through the CI/CD adapter — zero direct cloud SDK calls, grep-verifiable.
- [ ] `ApprovalGate`(deployment) fires and blocks progress until approved, for every deployment attempt.
- [ ] Simulated health failure correctly triggers automated rollback via the adapter.
- [ ] A detected incident spawns a genuinely new `Task` with correct lineage, without mutating or resuming the original task's graph — verified by inspecting both tasks' independent, correct terminal states.

## Risks

- **Risk:** Simulating CI/CD and health signals at this phase means the real integration risk (actual pipeline quirks, real health-metric noise) is deferred, not eliminated. **Mitigation:** explicitly flagged as a Phase 14 (real CI/CD via git provider MCP or webhook) and ongoing production-readiness concern (Phase 16) — this phase proves the *pattern* is correct, not that it's battle-tested against a real pipeline.

## Future Improvements

- Real canary-analysis thresholds (auto-promote/HITL/rollback bands) — a genuine gap the blueprint's comparative analysis (§0.1) names as a V2 strength worth incorporating; a good candidate to formalize once real deployment telemetry exists (Phase 13+/16).
- Real CI/CD pipeline integration — Phase 14.

## Research Opportunities

None yet — becomes relevant once Phase 16's chaos testing exercises this section's failure paths against more realistic conditions.
