"""SDLCState and every nested TypedDict from `final_plan.md` §B.2.

Reducers matter: `append_only` accumulates concurrent writes (Phase 06 fan-out).
`execution_plan` replaces. `messages` uses LangGraph `add_messages` and is the
human/system transcript only — never agent-to-agent traffic.
`agent_events` is UI/audit only; no node may read it for routing.
There is no `task_state` field — Postgres `tasks.state` is the phase source of truth.
There is no `TaskDecomposition.execution_order` field.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages

from common.task import Task


def append_only(existing: list, new: list) -> list:
    """Concatenate. Never replace. Used for every concurrent-write channel."""
    return existing + new


class RequirementsSpec(TypedDict):
    functional: list[str]
    non_functional: dict[str, str]
    acceptance_criteria: list[str]
    open_ambiguities: list[str]
    assumptions: list[str]
    out_of_scope: list[str]
    version: int
    approved_at: datetime | None
    approved_by: str | None


class ArchitectureDoc(TypedDict):
    component_boundaries: list[dict]
    api_contracts: list[dict]
    database_design: dict
    security_design: dict
    deployment_strategy: str
    adr_ids: list[str]
    version: int
    approved_at: datetime | None


class TaskDecomposition(TypedDict):
    """WHAT the work is. Do not add `execution_order` — the scheduler ignores it."""

    tasks: list[dict]
    ownership_map: dict[str, str]
    version: int


class SubtaskDependencyEdge(TypedDict):
    from_subtask: str
    to_subtask: str
    kind: Literal[
        "produces_interface",
        "file_overlap",
        "symbol_overlap",
        "shared_resource",
        "build_order",
        "test_coupling",
        "declared",
        "discovered",
    ]
    blocking: bool
    evidence: str
    source: Literal["manager_declared", "repo_intelligence", "runtime_discovery"]
    confidence: float


class SubtaskDependencyGraph(TypedDict):
    nodes: list[str]
    edges: list[SubtaskDependencyEdge]
    plan_version: int
    ri_available: bool


class ExecutionWave(TypedDict):
    wave_index: int
    subtask_ids: list[str]
    width: int
    rationale: str


class ExecutionPlan(TypedDict):
    """WHEN the work runs. Replace-semantics on SDLCState.execution_plan."""

    plan_version: int
    task_id: str
    waves: list[ExecutionWave]
    topology_class: Literal["sequential", "parallel", "hybrid"]
    max_wave_width: int
    dispatch_concurrency: int
    dependency_graph: SubtaskDependencyGraph
    created_from: Literal["initial_plan", "amendment", "replan"]
    superseded_plan_version: int | None


class TopologyDecisionRecord(TypedDict):
    decision_id: str
    task_id: str
    plan_version: int
    topology_class: Literal["sequential", "parallel", "hybrid"]
    subtask_count: int
    wave_count: int
    widths: list[int]
    blocking_edge_count: int
    advisory_edge_count: int
    features: dict
    policy_rules_fired: list[str]
    width_cap_source: str
    fail_closed_reason: str | None
    created_from: Literal["initial_plan", "amendment", "replan"]
    created_at: datetime


class WaveHandoffNote(TypedDict):
    task_id: str
    plan_version: int
    covers_waves: list[int]
    for_wave: int
    interfaces_changed: list[dict]
    files_touched: list[str]
    discovered_dependencies: list[str]
    constraints_for_next_waves: list[str]
    unresolved_issues: list[str]
    artifact_refs: list[str]
    token_budget: int
    truncated: bool


class ImplementationResult(TypedDict):
    subtask_id: str
    worker_id: str
    attempt_number: int
    plan_version: int
    wave_index: int
    diff_ref: str
    touches_files: list[str]
    status: Literal["validated", "blocked", "failed"]


class QAEvidence(TypedDict):
    static_analysis: dict | None
    security_findings: list[dict]
    mutation_score: float | None
    property_violations: list[dict]
    exploratory_findings: list[dict]
    spec_compliance: dict
    coverage_delta: float | None
    risk_score: float
    recommendation: Literal["pass", "pass_with_warnings", "fail"]


class DeploymentRecord(TypedDict):
    strategy: Literal["rolling", "blue_green", "canary"]
    target_env: str
    pipeline_run_id: str | None
    canary_metrics: dict | None
    health_status: Literal["healthy", "degraded", "failed"] | None
    rollback_triggered: bool
    deployed_at: datetime | None


class ValidationFlag(TypedDict):
    source: str
    agent_id: str
    phase: str
    flag_type: Literal[
        "schema_violation",
        "semantic_drift",
        "confidence_below_threshold",
        "tool_error",
        "spec_inconsistency",
        "design_gap",
        "security_finding",
    ]
    severity: Literal["info", "warning", "error", "critical"]
    detail: str
    rollback_to: str | None


class HITLRequest(TypedDict):
    """Data record of a pending human question. Distinct from LangGraph interrupt()."""

    request_id: str
    request_type: Literal["clarification", "approval", "policy_review", "risk_approval"]
    phase: str
    reason: str
    evidence_ref: str
    options: list[str]
    response: str | None
    responded_by: str | None
    responded_at: datetime | None
    timeout_at: datetime


class WorkerCoordinationPacket(TypedDict):
    subtask_id: str
    worker_id: str
    plan_version: int
    wave_index: int
    assumptions: list[str]
    discovered_dependencies: list[str]
    interface_changes: list[dict]
    risks: list[str]
    touches_files: list[str]
    confidence: float
    needs_manager_attention: bool
    blocked: bool
    artifact_refs: list[str]


class ClarificationEscalation(TypedDict):
    escalation_id: str
    subtask_id: str
    worker_id: str
    category: Literal[
        "missing_context",
        "broken_assumption",
        "interface_conflict",
        "scope_ambiguity",
    ]
    question: str
    evidence_refs: list[str]
    proposed_default: str | None
    confidence: float
    ri_consulted: bool
    created_at: datetime
    resolved_at: datetime | None
    resolution: Literal["redispatched", "hitl_resolved", "superseded"] | None


class ReplanContext(TypedDict):
    task_id: str
    attempt_number: int
    previous_decomposition: TaskDecomposition
    previous_plan: ExecutionPlan
    previous_topology_decision: TopologyDecisionRecord
    completed_wave_indices: list[int]
    previous_assumptions: list[str]
    validator_findings: list[dict]
    wcp_summaries: list[str]
    unresolved_clarifications: list[ClarificationEscalation]
    prior_manager_decisions: list[str]
    affected_worker_ids: list[str]
    repo_discoveries: list[str]
    discovered_edges: list[SubtaskDependencyEdge]
    unresolved_risks: list[str]


class ContextLedgerEntry(TypedDict):
    fact_id: str
    task_id: str
    kind: Literal[
        "decision",
        "constraint",
        "interface",
        "assumption",
        "discovered_fact",
        "unresolved_issue",
        "error",
        "validation_result",
    ]
    subject: str
    statement: str
    provenance_refs: list[str]
    phase: str
    plan_version: int | None
    wave_index: int | None
    confidence: float
    status: Literal["active", "superseded", "resolved"]
    created_at: datetime


class SDLCState(TypedDict):
    # Identity
    task_id: str
    workflow_profile_id: str | None

    # Phase artifacts
    requirements: RequirementsSpec | None
    architecture: ArchitectureDoc | None
    task_decomposition: TaskDecomposition | None
    implementation_results: Annotated[list[ImplementationResult], append_only]
    qa_evidence: QAEvidence | None
    deployment_record: DeploymentRecord | None

    # Execution topology — plan replaces; decisions/notes accumulate
    execution_plan: ExecutionPlan | None
    plan_version: int
    current_wave_index: int
    topology_decisions: Annotated[list[TopologyDecisionRecord], append_only]
    wave_handoff_notes: Annotated[list[WaveHandoffNote], append_only]
    plan_amendment_count: int
    demotion_ignore_keys: list[dict]

    # Communication. messages = humans/system only.
    messages: Annotated[list, add_messages]
    agent_events: Annotated[list[dict], append_only]
    feedback_reports: Annotated[list[dict], append_only]
    worker_coordination_packets: Annotated[list[dict], append_only]
    clarification_escalations: Annotated[list[dict], append_only]

    # Validation & safety
    validation_flags: Annotated[list[ValidationFlag], append_only]
    rollback_count: int
    current_rollback_target: str | None

    # HITL: queue is the in-graph pending set (replace); history is append_only
    hitl_queue: list[HITLRequest]
    hitl_history: Annotated[list[HITLRequest], append_only]

    intent_version: int
    intent_last_updated: datetime | None

    context_ledger: Annotated[list[ContextLedgerEntry], append_only]
    compaction_events: Annotated[list[dict], append_only]

    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    phase_costs: dict[str, float]


def initial_sdlc_state(task: Task) -> SDLCState:
    """Empty working state for one Task. Stub nodes fill phase fields as they run."""
    return {
        "task_id": task.id,
        "workflow_profile_id": task.workflow_profile_id,
        "requirements": None,
        "architecture": None,
        "task_decomposition": None,
        "implementation_results": [],
        "qa_evidence": None,
        "deployment_record": None,
        "execution_plan": None,
        "plan_version": 0,
        "current_wave_index": -1,
        "topology_decisions": [],
        "wave_handoff_notes": [],
        "plan_amendment_count": 0,
        "demotion_ignore_keys": [],
        "messages": [],
        "agent_events": [],
        "feedback_reports": [],
        "worker_coordination_packets": [],
        "clarification_escalations": [],
        "validation_flags": [],
        "rollback_count": 0,
        "current_rollback_target": None,
        "hitl_queue": [],
        "hitl_history": [],
        "intent_version": 0,
        "intent_last_updated": None,
        "context_ledger": [],
        "compaction_events": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": 0.0,
        "phase_costs": {},
    }
