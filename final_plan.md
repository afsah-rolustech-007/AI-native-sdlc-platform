# AI-Native SDLC Orchestration Platform

## Definitive Engineering Specification — Version 3.0

> **Status:** Implementation-Ready  
> **Supersedes:** `FINAL_BLUEPRINT_V2.md` and `AI-Native_SDLC_Platform_Blueprint_FINAL.md`  
> **Start here:** §B.3 (Task Data Model) → §B.6 (Confidence Model) → §B.2 (Fail-Closed) → §E.1 (Agent Templates) → §F.3 (Routing Rules)

---

# Part 0 — Comparative Analysis & Design Decisions

Both prior blueprints represent serious engineering work. V3 is not a merge — it is a redesign that takes the strongest solution from each area.

## 0.1 Decision Matrix: V2 vs. AI-Native (FINAL) vs. V3


| Area                        | V2 Strength                                                                                     | AI-Native Strength                                                                                                                                   | V3 Decision                                                                                                                                                                                                                                                                         |
| --------------------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Task Data Model**         | Detailed `SDLCState` TypedDict with all reducers                                                | Richer task schema with `lineage`, `budget`, `domain_shard` fields                                                                                   | **AI-Native wins.** Its `Task` model is a first-class object queryable by routing, audit, and evaluation — not just graph state. V3 adopts this with V2's `SDLCState` reducers                                                                                                      |
| **Confidence Model**        | Requirements-phase completeness scorer only                                                     | 4-signal composite formula with calibration path, Fail-Closed behavior, and stated v1 weights                                                        | **AI-Native wins.** A load-bearing gate defined as a weighted formula with an empirical calibration path is strictly superior to a single-phase completeness rubric                                                                                                                 |
| **Fail-Closed Principle**   | Not stated as a principle; implied by MASC                                                      | Explicit Principle 8: any internal failure routes toward more oversight, never more autonomy                                                         | **AI-Native wins.** This is the most important safety design decision in the entire platform and belongs as an axiom, not an implication                                                                                                                                            |
| **Workflow Engine**         | Detailed `WorkflowContext` schema + `@property` derived fields                                  | `WorkflowProfile` + ordered first-match-wins `resolve_workflow_profile()` function                                                                   | **Combined.** V2's richer `WorkflowContext` schema feeds V3; AI-Native's `resolve_workflow_profile()` ordered rule function is the right execution model. V3 uses both                                                                                                              |
| **MASC / Validation**       | Fully specified 3-check MASC engine (schema → confidence → semantic drift) with token costs     | `Validator` template as a reusable config-parametrized pattern, not bespoke classes                                                                  | **Combined.** MASC from V2 (post-node middleware, cheapest-first) + AI-Native's `Validator` template (parametrized per phase). Eliminates both the naming-without-specifying problem and the bespoke-class explosion problem                                                        |
| **Agent Design**            | 18+ agents, all individually specified                                                          | Two reusable templates (`ApprovalGate`, `Validator`) + phase-level agent tables                                                                      | **AI-Native wins.** Bespoke agents for patterns that are the same design is unjustified complexity. V3 uses templates for patterns, full specs only for genuinely distinct agents                                                                                                   |
| **Requirements Engine**     | Detailed question dependency graph, auto-skip via repo context, confidence-gated exit           | Same design, called "Dynamic Questioning Engine," as a dedicated phase and package                                                                   | **Combined.** V2's question dependency graph is more detailed; AI-Native's promotion to a first-class phase and package is the right architectural signal. V3 adopts both                                                                                                           |
| **Rollback Design**         | Explicit rollback graph: failure type → reentry point + max depth                               | Two separate concerns: code rollback (git branch) vs. orchestration rollback (checkpoint replay)                                                     | **AI-Native wins** on the conceptual separation. V3 keeps the separation clearly and adds V2's explicit rollback targets                                                                                                                                                            |
| **Memory Architecture**     | 5 memory scopes; inter-phase artifact contracts with token budgets                              | 4 physical tiers + named scope reconciliation table + Phase Handoff Packets                                                                          | **Combined.** AI-Native's `PhaseHandoffPacket` is the right mechanism. V2's token budget contracts per phase transition are the right constraints. V3 uses both                                                                                                                     |
| **Repository Intelligence** | SCIP + Tree-sitter + KuzuDB; sharded parallel indexer; `RepositoryIntelligence` API             | Layered index (L0–L4); Tree-sitter + Zoekt + pgvector → Qdrant; NetworkX → Neo4j; federated shards; Aider-style repo map                             | **AI-Native wins on tooling.** Zoekt over SCIP for search (Zoekt is battle-proven at Sourcegraph scale); NetworkX→Neo4j migration path is cleaner than KuzuDB (less mature, embedded-only); Aider repo map is a proven token-efficiency technique. V3 adopts AI-Native's tool stack |
| **Context Engineering**     | Full budget math derived from model window; 5-step compression pipeline; tool contracts         | AST-boundary chunking; dependency-aware expansion; hierarchical summaries; progressive loading; Phase Handoff Packets; Aider-style PageRank repo map | **Combined.** V2's budget math is the right foundation; AI-Native's compression techniques and Aider repo map are superior to V2's ad-hoc compression; V3 combines them                                                                                                             |
| **Model Routing**           | Runtime `ModelRouter` with capability scoring × cost × risk                                     | Rule-based tiering + `escalate_model_tier()` on repeated rejection; LangChain `BaseChatModel` as adapter                                             | **Combined.** AI-Native's `escalate_model_tier()` pattern is more auditable than V2's scoring function (less black-box); LangChain as base is pragmatic. V3 uses AI-Native routing + V2's capability-requirement table as the tiering guide                                         |
| **QA**                      | 14-tool activation matrix; regression test generation; 80% tools are deterministic              | Risk-tiered QA routing; CodeQL for deep scans alongside Semgrep; test-impact analysis via dependency graph                                           | **Combined.** V2's activation matrix; AI-Native's CodeQL (deep periodic) + Semgrep (fast inline) split; test-impact analysis from AI-Native. V3 uses all three                                                                                                                      |
| **Deployment**              | Canary analysis (auto-promote < 5% delta; HITL 5–15%; rollback > 15%); strategy selection rules | Deployment via existing CI/CD pipelines only; no direct cloud API calls                                                                              | **Combined.** V2's canary analysis thresholds + AI-Native's "agents never call cloud APIs directly" safety boundary. Both are correct and non-redundant                                                                                                                             |
| **Evaluation**              | Automated post-task scoring pipeline; Fix Rate; Attribution Accuracy                            | Golden dataset; shadow-mode graduation; DORA metrics; platform self-eval; feedback-loop health KPIs                                                  | **AI-Native wins.** Shadow-mode graduation (evidence-based trust escalation) is a critical safety mechanism missing from V2. Feedback-loop health KPIs are a genuine gap. V3 adopts all of AI-Native's evaluation framework                                                         |
| **Production Readiness**    | Risk table with mitigations; RBAC matrix                                                        | Consolidated Part N with named categories; Postgres SPOF flagged for future split; consumer-group queue partitioning                                 | **AI-Native wins.** More systematic; names categories V2 missed (queue starvation, trace retention, tool supply-chain risk)                                                                                                                                                         |
| **Tech Stack**              | Complete 35+ tool table with versions                                                           | Recommendations with rationale + alternatives tables                                                                                                 | **Combined.** V3 includes both the reasoning (AI-Native) and the versions (V2)                                                                                                                                                                                                      |
| **Project Structure**       | V2 directory tree                                                                               | AI-Native directory tree with `requirements_engine/`, `chaos/` tests, `configs/` for versioned policies                                              | **AI-Native wins.** Cleaner separation; `chaos/` test suite and versioned policy configs are the right production engineering decisions                                                                                                                                             |
| **UI**                      | 10 screens with WebSocket event protocol; data contracts per screen                             | 11 screens, thin read layer, clarity over visualization                                                                                              | **Combined.** AI-Native's 11 screens + V2's WebSocket protocol and data contracts. V3 keeps both                                                                                                                                                                                    |
| **Security**                | RBAC matrix; prompt injection defense; sandboxing                                               | Sandboxing; least-privilege for MCP/tool credentials specifically; prompt injection classifier                                                       | **AI-Native adds** explicit MCP/tool credential scoping. V3 combines: RBAC from V2 + tool credential scoping from AI-Native                                                                                                                                                         |




## 0.2 Net New Decisions in V3 (Neither Document Had These)


| #   | Decision                                           | Rationale                                                                                                                                                                                                                                                                      |
| --- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | **Feedback Agent** as a named role                 | Neither document adequately specified what happens *after* N consecutive failures on the same module. The AI-Native blueprint names it but only in agent tables. V3 specifies its behavior explicitly                                                                          |
| 2   | **Structured prompt engineering strategy**         | V2 correctly identified this as a gap and added "structured outputs" but still no design. V3 adds a concrete approach: Output Schema Protocol, system role template, and context injection ordering                                                                            |
| 3   | **Agent specialization techniques**                | Neither blueprint addressed the user's explicit request to go beyond system prompts. V3 adds a dedicated section on specialization: structured reasoning patterns, reflection, planner-executor, self-critique, and when fine-tuning is justified                              |
| 4   | **KuzuDB → dropped in favor of NetworkX→Neo4j**    | KuzuDB is an embedded columnar graph DB. For a platform where the graph is a long-lived shared service queried concurrently across tasks (as correctly identified in AI-Native D.1), embedded-only is a design mismatch. NetworkX (MVP) → Neo4j (at scale) is the correct path |
| 5   | **Zoekt over SCIP as the primary search engine**   | SCIP is a protocol for writing language-server symbol data; it is not a search engine. V2 incorrectly positioned SCIP as a search engine. Zoekt is a proven trigram search index; Tree-sitter provides symbol resolution. Both are needed, serving different functions         |
| 6   | **Monitoring → spawns new Task, never loops back** | AI-Native correctly identified this. V3 makes it a design axiom: production incidents get fresh risk/confidence assessment, not an assumption that the original task's context still applies                                                                                   |


---



# Part A — Vision, Scope & Non-Goals



## A.1 Vision

A reliable, semi-autonomous AI Software Engineering platform that orchestrates the complete SDLC — requirements through maintenance — as a coordinated engineering organization. It optimizes for **correctness, architectural quality, reliability, maintainability, security, cost efficiency, and explainability** over raw code-generation throughput. Large-repository awareness (100k–1M+ files) is a first-class design constraint, not an optimization pass.

## A.2 Core Principles

1. **Planning outweighs implementation.** Reasoning budget front-loads into requirements and design. Implementation is delegated to cheaper models once design is approved.
2. **Narrow-scoped agents, validated at every handoff.** No artifact moves to the next phase without passing a validator agent independent of the one that produced it.
3. **Human supervision replaces prompt engineering for ambiguity.** Ambiguity triggers structured clarification, not silent assumption.
4. **Irreversible actions require human approval, not confidence alone.** Confidence scores inform routing speed; they never unlock autonomy over production deploys, force-pushes, or data migrations.
5. **Deterministic and auditable over clever and opaque.** Rule-based routing, policy tables, and named tools are preferred over learned/black-box equivalents wherever both are viable.
6. **Model- and tool-independence is structural.** Enforced via adapter interfaces, not convention.
7. **Incremental over big-bang.** Useful on a 500-file repo on day one; scales to 1M+ files by strengthening the same architecture.
8. **Fail-Closed by Default.** Any internal scoring, policy, or validation mechanism that errors, times out, or returns malformed output routes the task toward *more* human oversight, never toward *more* autonomy. A broken Confidence Scorer does not default to "assume high confidence" — it defaults to "require approval." This applies uniformly across every Part of this document.
9. **Intentional worker isolation.** Parallel workers are deliberately unaware of sibling workers. Cross-worker knowledge is delayed until Fan-in, never exchanged mid-flight. This is not a limitation — it is what preserves determinism, auditability, reproducibility, reasoning quality, deadlock avoidance, and safe parallelism at scale. The communication invariant (§D.9.1) is the operational expression of this principle; Fan-in is where intentional cross-branch knowledge is first assembled.



## A.3 Non-Goals

- Not a general-purpose autonomous coding agent for arbitrary unscoped requests — task/ticket-driven with structured intake.
- Not a replacement for human architects on irreversible or high-blast-radius decisions.
- Not a real-time interactive pair-programming tool — async, review-gated by design.
- Multi-tenancy is explicitly deferred post-MVP.

---



# Part B — Core Data Model & Foundational Specifications



## B.1 Task Data Model

Every unit of work is a `Task` — the single most important structural decision. Nothing else (routing, memory, feedback loops, approvals, evaluation) can be specified precisely without it.

```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from uuid import UUID
from datetime import datetime

class WorkType(str, Enum):
    NEW_PROJECT   = "new_project"
    FEATURE       = "feature"
    BUG           = "bug"
    HOTFIX        = "hotfix"
    REFACTOR      = "refactor"
    MIGRATION     = "migration"
    TECH_DEBT     = "tech_debt"
    MAINTENANCE   = "maintenance"

class Methodology(str, Enum):
    AGILE      = "agile"
    WATERFALL  = "waterfall"
    HYBRID     = "hybrid"

class RiskTier(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"

class TaskState(str, Enum):
    INTAKE          = "intake"
    REQUIREMENTS    = "requirements"
    DESIGN          = "design"
    IMPLEMENTATION  = "implementation"
    QA              = "qa"
    REVIEW          = "review"
    RELEASE         = "release"
    MONITORING      = "monitoring"
    DONE            = "done"
    BLOCKED         = "blocked"

class RepoRef(BaseModel):
    repo_id: str
    architecture: str                  # monolith | modular_monolith | microservices
    domain_shard: Optional[str] = None # Which RI shard this task touches (Part G.4)

class TaskBudget(BaseModel):
    token_ceiling: int       = 2_000_000  # Total tokens across all agents for this task
    cost_ceiling_usd: float  = 20.0
    max_retries_per_node: int = 3

class ApprovalRecord(BaseModel):
    checkpoint: str
    approver: str
    decision: str            # approve | reject_with_feedback | request_changes
    evidence_ref: str        # Blackboard pointer, not inlined
    timestamp: datetime

class Task(BaseModel):
    id: str                  = Field(max_length=255)  # PostgreSQL constraint enforced here
    title: str
    source: str              # user_request | ticket_import | monitoring_incident | maintenance_scan
    type: WorkType
    methodology: Methodology
    repo_refs: list[RepoRef]
    risk_tier: RiskTier
    confidence_score: float  = 0.0   # Computed by Confidence Model (B.4)
    state: TaskState         = TaskState.INTAKE
    workflow_profile_id: Optional[str] = None  # Set by Workflow Policy Engine (Part F)
    budget: TaskBudget       = Field(default_factory=TaskBudget)
    approvals: list[ApprovalRecord] = Field(default_factory=list)
    lineage: dict            = Field(default_factory=dict)  # {parent_task_id?, root_incident_id?}
    artifact_refs: list[str] = Field(default_factory=list)  # Blackboard pointers
    created_at: datetime     = Field(default_factory=datetime.utcnow)
```

**Why not a flat TypedDict:** `Task` must be queryable for routing, auditable for compliance, and validatable at write time. TypedDicts validate at type-check time only. Pydantic validates at runtime — the right behavior for a safety-critical object.

## B.2 LangGraph State (`SDLCState`)

`Task` is the durable record. `SDLCState` is the in-graph working state, keyed to the task, with `Annotated` reducers for parallel-safe merging.

```python
from __future__ import annotations
from typing import Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages
from datetime import datetime

def append_only(existing: list, new: list) -> list:
    return existing + new

class RequirementsSpec(TypedDict):
    functional: list[str]
    non_functional: dict[str, str]    # {nfr_type: spec}
    acceptance_criteria: list[str]
    open_ambiguities: list[str]       # Logged in PhaseHandoffPacket on exit
    assumptions: list[str]
    out_of_scope: list[str]
    version: int                      # Incremented on every mutation
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
    tasks: list[dict]                 # [{id, description, module, dependencies}]
    execution_order: list[list[str]]  # [[parallel_group], ...]
    ownership_map: dict[str, str]     # {module_path: sub_agent_id}

class ImplementationResult(TypedDict):
    """One entry per CodeGen branch outcome. Appended to SDLCState.implementation_results
    (append_only). Fan-in Coordinator reads entries with status='validated' for merge;
    'blocked' branches are paired with ClarificationEscalation entries instead."""
    subtask_id: str
    worker_id: str
    attempt_number: int
    diff_ref: str                     # Blackboard pointer — not inlined
    touches_files: list[str]          # cross-checked against WCP.touches_files at fan-in
    status: Literal["validated", "blocked", "failed"]
    # validated: passed Validator(implementation) for this attempt — eligible for fan-in merge
    # blocked:   worker stopped via ClarificationEscalation — fan-in batches, does not merge
    # failed:    validation exhausted or unrecoverable error on this attempt

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
    canary_metrics: dict | None       # {error_rate_delta, p99_latency_delta, saturation_delta}
    health_status: Literal["healthy", "degraded", "failed"] | None
    rollback_triggered: bool
    deployed_at: datetime | None

class ValidationFlag(TypedDict):
    """Output of MASC post-node validation and independent validator agents."""
    source: str                       # "masc" | "validator_agent" | "static_tool"
    agent_id: str
    phase: str
    flag_type: Literal["schema_violation", "semantic_drift", "confidence_below_threshold",
                        "tool_error", "spec_inconsistency", "design_gap", "security_finding"]
    severity: Literal["info", "warning", "error", "critical"]
    detail: str
    rollback_to: str | None           # Phase name if rollback recommended

class HITLRequest(TypedDict):
    """Every human-facing pause is one of these four types — never an untyped
    'question'. The `request_type` discriminant is what Phase 09's UI (Screens
    7/8) and RBAC filtering (§S) key off, replacing the earlier "type=clarification
    equivalent" convention with an explicit, schema-level field."""
    request_id: str
    request_type: Literal["clarification", "approval", "policy_review", "risk_approval"]
    phase: str
    reason: str
    evidence_ref: str                 # Blackboard pointer — not inlined
    options: list[str]
    response: str | None
    responded_by: str | None
    responded_at: datetime | None
    timeout_at: datetime

class WorkerCoordinationPacket(TypedDict):
    """Mandatory, structured self-report every parallel worker (CodeGen sub-agent,
    and any future Send-dispatched worker) emits on branch exit — success or stop.
    Produced as part of the SAME model call that produces the worker's primary
    output wherever possible (structured-output schema, §E.3), not a second LLM
    round-trip. This is what the Fan-in Coordinator (§D.4) reads to detect
    assumption drift and cross-worker interface conflicts that raw diffs alone
    would not surface until much later (Integration Validator, or worse, QA)."""
    subtask_id: str
    worker_id: str
    assumptions: list[str]                       # what the worker believed true
    discovered_dependencies: list[str]            # symbols/files touched beyond its assigned scope
    interface_changes: list[dict]                 # [{symbol, before, after}] — symbol MUST use RI symbol_id format (§G.6.1)
    risks: list[str]
    touches_files: list[str]                      # authoritative for fan-in overlap detection
    confidence: float
    needs_manager_attention: bool                 # True → Fan-in Coordinator must route to Manager
    blocked: bool                                 # True → this branch stopped; see ClarificationEscalation
    artifact_refs: list[str]                      # Blackboard pointers (diff, logs)

class ClarificationEscalation(TypedDict):
    """Emitted by a worker that cannot safely continue — either Repository
    Intelligence could not resolve what it needed, or a discovery invalidates
    an assumption baked into TaskDecomposition. A worker NEVER guesses past
    this point (Fail-Closed, Principle 8) and NEVER contacts another worker
    directly (§D.9's communication invariant) — it stops its own branch and
    escalates to the Manager, batched at fan-in. HITL is reached only if the
    Manager itself cannot resolve the escalation from ArchitectureDoc/RI."""
    escalation_id: str
    subtask_id: str
    worker_id: str
    category: Literal["missing_context", "broken_assumption", "interface_conflict", "scope_ambiguity"]
    question: str
    evidence_refs: list[str]                      # Blackboard pointers (what RI returned, if anything)
    proposed_default: str | None                  # Worker's best guess, never auto-applied
    confidence: float
    ri_consulted: bool                             # Must be True except for pure scope-ambiguity cases
    created_at: datetime
    resolved_at: datetime | None
    resolution: Literal["redispatched", "hitl_resolved", "superseded"] | None

class ReplanContext(TypedDict):
    """Structured history handed to a Manager on any replanning attempt (Feedback
    Agent revision, FL-05 re-assignment, or a Fan-in-Coordinator-triggered replan
    from flagged WCPs/ClarificationEscalations) so each attempt is strictly better
    informed than the last, rather than re-reasoning from scratch. This is what
    makes 'attempt_number' in FeedbackReport (§D.8) meaningful instead of cosmetic."""
    task_id: str
    attempt_number: int
    previous_decomposition: TaskDecomposition
    previous_assumptions: list[str]                # aggregated from prior WCPs
    validator_findings: list[dict]                 # prior FeedbackReport.validator_findings
    wcp_summaries: list[str]
    unresolved_clarifications: list[ClarificationEscalation]
    prior_manager_decisions: list[str]
    affected_worker_ids: list[str]
    repo_discoveries: list[str]                    # net-new facts surfaced since original decomposition
    unresolved_risks: list[str]

class SDLCState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────────
    task_id: str                      # task_id[:255] enforced at Task creation
    workflow_profile_id: str | None
    
    # ── Phase Artifacts ───────────────────────────────────────────────
    requirements: RequirementsSpec | None
    architecture: ArchitectureDoc | None
    task_decomposition: TaskDecomposition | None
    implementation_results: Annotated[list[ImplementationResult], append_only]
    qa_evidence: QAEvidence | None
    deployment_record: DeploymentRecord | None
    
    # ── Communication channels (append-only) ──────────────────────────
    # `messages` is EXCLUSIVELY the human/system conversation transcript (user
    # requests, HITL responses, system notices feeding the Intent Tracker,
    # §E.7). It is never a channel for agent-to-agent or worker-to-worker
    # communication — that traffic has its own typed channels below. See
    # §D.9's communication invariant for the rule this field must never violate.
    messages: Annotated[list, add_messages]
    agent_events: Annotated[list[dict], append_only]           # Observability only — UI/OTel, never control flow
    feedback_reports: Annotated[list[dict], append_only]  # Structured, not bare "try again"
    worker_coordination_packets: Annotated[list[dict], append_only]  # WorkerCoordinationPacket entries, this fan-out round
    clarification_escalations: Annotated[list[dict], append_only]    # ClarificationEscalation entries, open + resolved
    
    # ── Validation & Safety ───────────────────────────────────────────
    validation_flags: Annotated[list[ValidationFlag], append_only]
    rollback_count: int               # Hard cap at Task.budget.max_retries_per_node × phase_count
    current_rollback_target: str | None
    
    # ── HITL ──────────────────────────────────────────────────────────
    hitl_queue: list[HITLRequest]
    hitl_history: Annotated[list[HITLRequest], append_only]
    
    # ── Intent Tracking ───────────────────────────────────────────────
    intent_version: int
    intent_last_updated: datetime | None
    
    # ── Cost Tracking ─────────────────────────────────────────────────
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    phase_costs: dict[str, float]
```



## B.3 Memory Architecture (4 Physical Tiers)


| Tier           | Contents                                                                   | Lifetime                                       | Storage                                                      | Access Pattern                                                   |
| -------------- | -------------------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------- |
| **Working**    | `SDLCState` for active task; agent scratch reasoning                       | Task duration                                  | LangGraph state (in-memory + PostgreSQL checkpoint)          | All nodes in the active graph                                    |
| **Episodic**   | Completed task transcripts, outcomes, regression history                   | Indefinite, task-scoped                        | PostgreSQL + pgvector index                                  | Planning/Design agents (precedent search); Evaluation (Part L)   |
| **Semantic**   | Repository knowledge graph, architecture summaries, module ownership, ADRs | Indefinite, repo-scoped, incrementally updated | Graph DB (NetworkX→Neo4j) + Zoekt + pgvector                 | Almost every agent, via Repository Intelligence service (Part G) |
| **Procedural** | Distilled playbooks curated from episodic patterns; versioned policy rules | Indefinite, org-scoped                         | Versioned YAML/JSON configs; human-reviewed before promotion | Workflow Policy Engine (Part F)                                  |


**Key rules:**

- LangGraph state holds only Working memory. Episodic, Semantic, and Procedural are accessed via tool calls, never inlined into graph state. Keeps checkpoint size small and resume fast.
- Monitoring-detected incidents **do not loop back** into the original task's graph. They spawn a new `Task` linked via `lineage.root_incident_id`. A production incident requires a fresh risk/confidence assessment.
- At each phase transition, the outgoing phase writes a **Phase Handoff Packet** (§B.5). Incoming phase reads the packet as primary context; full upstream detail is retrieval-on-demand, not force-included.



### Memory Scope → Physical Tier Mapping


| Named Scope                    | Physical Tier                                      | Lifecycle                         |
| ------------------------------ | -------------------------------------------------- | --------------------------------- |
| Global / Org-wide memory       | Semantic + Procedural                              | Indefinite                        |
| Repository memory              | Semantic (per shard, §G.4)                         | Indefinite, incrementally updated |
| Workflow / Task memory         | Working (SDLCState)                                | Task duration                     |
| Phase memory                   | Working, scoped by phase + incoming Handoff Packet | Phase duration                    |
| Agent scratch memory           | Working (never persisted raw)                      | Single node invocation            |
| QA memory / Regression history | Episodic (QA slice)                                | Indefinite, feeds §K              |
| Historical execution memory    | Episodic                                           | Indefinite, feeds §B.4 and §F     |




## B.4 Confidence Model

Composite score from four measurable signals. A load-bearing gate — used to determine when requirements are sufficient to proceed to design, when to escalate model tier, and when auto-merge is eligible.

```
confidence_score = (
    0.35 × retrieval_coverage
  + 0.20 × precedent_strength
  + 0.30 × validator_agreement
  + 0.15 × static_check_cleanliness
)
```

- **retrieval_coverage** — did Repository Intelligence find sufficient relevant context?
- **precedent_strength** — how similar and successful are matched past tasks in episodic memory?
- **validator_agreement** — fraction of independent validators concurring.
- **static_check_cleanliness** — lint/type/security pass rate on the current artifact.

**Weights are v1 starter values.** Once shadow-mode data exists (§L.5), recalibrate via logistic regression against actual task outcomes. Run drop-one ablation first — `retrieval_coverage` and `validator_agreement` may correlate, effectively combining three signals.

**Fail-Closed (Principle 8):** if this computation fails, errors, or any input is unavailable — `confidence_score` is **not imputed**. The task is treated as below the confidence floor. Mandatory escalation.

### Phase-Specific Confidence Floors


| Phase          | Floor | Consequence Below Floor                                        |
| -------------- | ----- | -------------------------------------------------------------- |
| Requirements   | 0.80  | Continue questioning; HITL after 3 rounds without improvement  |
| Design         | 0.85  | Return to System Architect with specific gaps                  |
| Implementation | 0.75  | Escalate model tier (§F.3); Feedback Agent after 2nd rejection |
| QA             | 0.90  | Block deployment; HITL required                                |
| Deployment     | 0.95  | Mandatory HITL regardless of risk tier                         |




## B.5 Phase Handoff Packet

The mechanism that bounds context growth across phase transitions. Without this, context grows unboundedly across feedback-loop revisits.

```yaml
PhaseHandoffPacket:
  from_phase: enum[intake, requirements, design, implementation, qa, review, release]
  to_phase: enum
  decisions: [{topic, decision, rationale_ref}]  # rationale_ref = blackboard pointer, not inlined
  open_assumptions: [string]                       # What confidence exit condition (b) logs
  confidence_at_handoff: float
  artifact_refs: [blackboard_ref]                  # Full artifacts available on demand, not injected
  size_budget_tokens: int                          # Hard cap; lowest-relevance items drop to pointer-only
```

Incoming phase manager reads this packet as primary context. Full upstream detail is retrieved via tool call only if the incoming agent's own retrieval step determines it's actually needed.

**Token cap per transition:**


| Transition                             | Max Tokens in Packet |
| -------------------------------------- | -------------------- |
| Requirements → Design                  | 2,000                |
| Design → Implementation (manager)      | 3,000                |
| Design → Implementation (per sub-task) | 1,500                |
| Implementation → QA                    | 2,000                |
| QA → Deployment                        | 1,000                |
| Any → HITL                             | 3,000                |




## B.6 Security Model

- **Execution sandboxing:** every agent that runs code or shell commands does so inside an ephemeral, network-restricted container, scoped to one task, destroyed on completion regardless of outcome.
- **Least-privilege repo access:** short-lived, task-scoped git tokens with only the permissions the task's risk tier requires.
- **MCP/tool credential scoping:** the same least-privilege principle applies explicitly to QA tools, static analyzers, MCP servers, and dependency scanners — not just repo tokens. A compromised linter plugin or malicious MCP server is a real attack surface.
- **Prompt-injection defense:** issue text, PR descriptions, comments, and any external content entering Repository Intelligence is treated as untrusted data, never as instructions. A lightweight classifier flags content containing imperative/instructional patterns before it's summarized into semantic memory.
- **Secrets redaction:** a pre-context-assembly filter strips credential-shaped strings before any repo content enters a model call.
- **No standing production credentials.** Deployment actions execute through existing CI/CD pipelines under human-approved gates. Agents never call cloud provider APIs directly.
- **Release governance:** agents never push to protected branches. All code changes land via pull request. Auto-merge only when: risk tier is Low, full QA suite is green, and `confidence_score > AUTO_MERGE_CEILING`. Medium/High/Critical always require human-approved merge.



## B.7 Cost Governance

- Every Task carries a `budget` (`token_ceiling`, `cost_ceiling_usd`, `max_retries_per_node`). **Until Phase 10:** `Task.budget` is initialized with §B.1 defaults at task creation (`token_ceiling=2_000_000`, `cost_ceiling_usd=20.0`, `max_retries_per_node=3`). Phase 10's `resolve_workflow_profile()` may override `cost_budget_usd` and related limits per task — it does not replace the safety ceilings, only tunes them within bounds.
- **From Phase 10 onward:** `resolve_workflow_profile()` sets `WorkflowProfile.cost_budget_usd` at intake; the Planning Manager (or intake node) writes the resolved value onto `Task.budget` before downstream agents run.
- A **kill-switch node** wraps the graph: any task exceeding budget OR a global max-node-visits count is force-routed to human-escalation state.
- Per-task cost is tracked per agent, per phase, and exported to the evaluation framework.
- Model routing (§F.3) defaults to cheaper models; escalates to larger models only on validator rejection or low confidence.



## B.8 Observability & Telemetry Contract

Observability is a supporting system, not an orchestration concern. LangGraph is one orchestrator implementation. Evaluation (§L) must never import LangGraph types.

```
Any Orchestrator  →  TelemetrySink (this section)  →  OTel adapter  →  OTLP exporter  →  backend
                                                                                         (console | Langfuse | collector)
EvaluationEngine (§L)  ←  TelemetrySink export + SDLCState artifacts + Postgres tables
```

**Hard rules**

1. Orchestration code talks only to `TelemetrySink`. It never imports OTel, Langfuse, or LangSmith SDKs.
2. Telemetry failure never fails a task: every `TelemetrySink` method swallows exporter errors, logs them, and returns. Proven by test from Phase 00 §05.
3. `AgentEvent` (§P) is a **UI projection** of telemetry + state changes. It is not the telemetry contract and is not an evaluation input for scoring (UI may display scores after §L writes them).
4. Typed SDLCState (WCP, ClarificationEscalation, FeedbackReport, ValidationFlag, PhaseHandoffPacket) remains the **source of truth for content**. Telemetry records that those objects were produced (IDs + Blackboard refs), not a second copy of their payloads.
5. No graph node, Manager, Fan-in Coordinator, Validator, or policy function may read telemetry or `agent_events` to decide routing. Same rule as §P.

### B.8.1 What is a trace vs a span vs an event vs a metric vs a log

| Kind | Used for | Why |
|---|---|---|
| **Trace** | One `Task` execution (`trace_id` = task-scoped, set at graph invoke) | Reconstruct the whole run. One parent for all child work. |
| **Span** | Timed unit of work with start/end: PHASE, MANAGER, AGENT, LLM_CALL, TOOL_CALL, VALIDATION, FAN_IN, HITL, SANDBOX | Latency, status, parent/child. Enough to rebuild Decision → Action → Result. |
| **Event** (span event) | Instant facts that are not themselves timed work: WCP emitted, clarification raised, feedback-loop fired, kill-switch tripped, serialize-and-rerun | Cheap; does not invent fake durations. |
| **Attribute** | IDs, model/provider, tokens, cost, status, retry count, tool name, Blackboard refs | Indexed, queryable, size-bounded. Never dump full diffs or prompts here at MVP. |
| **Metric** | Counters/histograms: tokens, cost_usd, latency_ms, retries, validation_fail, tool_fail | Aggregates for dashboards (Prometheus from Phase 15). Not a substitute for traces. |
| **Log** (`structlog`) | Human-readable diagnostics bound to `task_id` + `trace_id` | Debug when a span is not enough. Same correlation IDs. |

Do **not** model every log line as a span. Do **not** inline full LLM prompts/completions into attributes at MVP (store Blackboard pointer `prompt_ref` / `output_ref` only if a later eval case needs them; Phase 15 may enable opt-in capture per experiment).

### B.8.2 Span hierarchy (required parent/child)

```
TASK (task_id)
 └── PHASE (phase)
      └── MANAGER (manager_id)           # omitted for template-only steps
           └── AGENT (agent_id)
                ├── LLM_CALL (model_id, provider, tokens, cost)
                ├── TOOL_CALL (tool_name, args_digest, result_status)
                ├── VALIDATION (validator_id or masc, pass/fail)
                └── [retry: sibling AGENT span with attempt_number++]
      └── FAN_IN                          # implementation phase only
      └── HITL                            # interrupt wait; duration = wall clock until resume
```

Parallel `Send` branches are sibling AGENT spans under the same MANAGER span. Fan-in is a sibling of those agents, not a child of one worker.

### B.8.3 `TelemetrySink` Protocol (canonical interface)

Implemented in `packages/common/telemetry.py`. The OTel SDK lives only in `packages/common/tracing.py` as `OtelTelemetrySink(TelemetrySink)`.

```python
from typing import Protocol, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Literal

SpanKind = Literal[
    "task", "phase", "manager", "agent",
    "llm_call", "tool_call", "validation", "fan_in", "hitl", "sandbox",
]

class TelemetrySink(Protocol):
    """Never raises. Never used for control flow."""

    def start_span(
        self,
        *,
        kind: SpanKind,
        name: str,
        task_id: str,
        phase: str | None = None,
        manager_id: str | None = None,
        agent_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict | None = None,
    ) -> str: ...
    """Returns span_id. No-op sink returns a dummy id."""

    def end_span(
        self,
        span_id: str,
        *,
        status: Literal["ok", "error", "cancelled"],
        error_type: str | None = None,
        error_message: str | None = None,
        attributes: dict | None = None,
    ) -> None: ...

    def emit_event(
        self,
        span_id: str,
        *,
        name: str,
        attributes: dict | None = None,
    ) -> None: ...

    def record_metric(
        self,
        name: str,
        value: float,
        *,
        unit: str,
        attributes: dict | None = None,
    ) -> None: ...

    @contextmanager
    def span(self, **kwargs) -> Iterator[str]: ...
    """start_span / end_span with status=error on exception; does not swallow the exception."""
```

`emit_node_event(...)` from Phase 00 is kept as a **thin compatibility helper** that opens/closes a single span with the original fields (`task_id, node_id, agent_id, phase, model_id, input_tokens, output_tokens, cost_usd, latency_ms, validation_result`). New call sites (Phase 01+) use `TelemetrySink.span` / `start_span`. Do not grow `emit_node_event` with new parameters — extend attributes on `TelemetrySink` instead.

### B.8.4 Required attributes (MVP)

Always set when known. Empty/null allowed (sandbox-only spans in Phase 00).

| Attribute | Span kinds | Notes |
|---|---|---|
| `task_id` | all | Same as `Task.id` / LangGraph `thread_id[:255]` |
| `trace_id` | all | OTel trace id; bound into structlog |
| `span_id` / `parent_span_id` | all | Parent/child |
| `phase` | phase and below | `TaskState` value |
| `manager_id` | manager and below | e.g. `implementation_manager` |
| `agent_id` | agent and below | e.g. `codegen`, `validator.implementation` |
| `operation` | llm_call | `(phase, operation)` key from §I.2 `CAPABILITY_REQUIREMENTS` |
| `model_id` / `provider` | llm_call | From `ModelAdapter`, never hardcoded |
| `input_tokens` / `output_tokens` / `cost_usd` | llm_call | From Phase 02 pricing registry, not provider cost fields |
| `latency_ms` | timed spans | End − start |
| `attempt_number` | agent, llm_call | Aligns with worker idempotency key (§D.9.8) |
| `subtask_id` | agent (CodeGen) | Fan-out identity |
| `tool_name` | tool_call | Exact registered tool id |
| `tool_args_digest` | tool_call | Hash or redacted summary — never secrets (§B.6) |
| `tool_status` | tool_call | ok / error / timeout |
| `validation_result` | validation | pass / fail + flag_type if fail |
| `artifact_ref` | events | Blackboard pointer, not payload |
| `experiment_id` | task | Set only when a Phase 15 experiment run invokes the graph |

### B.8.5 Orchestration adapter (LangGraph is an implementation detail)

`packages/orchestration/telemetry_adapter.py` (Phase 01) wraps node functions:

- On node entry: `start_span(kind="phase"| "manager"| "agent", ...)` and `update_task_state` (§D.2.1).
- On node exit: `end_span`.
- On `Send` fan-out: each branch span shares the manager parent; do not create a LangGraph-specific "Send span" kind.
- On `interrupt()`: `start_span(kind="hitl")`; on `Command(resume=...)`: `end_span`.

If the orchestrator is replaced, **only this adapter file changes**. `TelemetrySink`, §L evaluators, and UI `AgentEvent` mapping stay.

`packages/model_adapters/telemetry.py` (Phase 02) records `llm_call` spans around every `ModelAdapter.complete` / `stream` / `call_tools` / `embed`. It must call `TelemetrySink`, not OTel directly.

`BaseAgent.run()` (Phase 05) records the AGENT span, child LLM spans (via adapter), TOOL_CALL spans per tool, VALIDATION span for MASC.

Fan-in Coordinator (Phase 06) records a FAN_IN span plus events: `overlap_detected`, `semantic_conflict`, `serialize_and_rerun`, `replan_triggered` — attributes are booleans/counts/subtask_ids, not diffs.

### B.8.6 Correlation with existing stores

| Data | Store | Telemetry role |
|---|---|---|
| Cost / tokens | `cost_tracking` (§R) | Duplicate of llm_call attributes; table remains source of truth for budget kill-switch |
| HITL | `hitl_log` + `SDLCState.hitl_queue` (§D.7.1) | HITL span duration; do not score from spans |
| WCP / escalations | `SDLCState` append-only lists | Event `wcp_emitted` with `subtask_id` |
| Validation | `ValidationFlag` / MASC | VALIDATION span |
| UI live view | `AgentEvent` / Redis pubsub | Mapped from sink callbacks in `emit_node_event` / adapter — one writer |

Full trace retention target: 90 days. Episodic summaries: indefinite (§B.3). Not enforced in Phase 00.

### B.8.7 Tool / research choices (observability only)

| Tool | Role in *this* project | Decision |
|---|---|---|
| **OpenTelemetry Python** | Traces + (later) metrics export | **Adopt** as the sink implementation. GenAI semantic conventions: map our attributes onto `gen_ai.*` where they match (`gen_ai.request.model`, token usage); keep project attributes (`sdlc.phase`, `sdlc.agent_id`) as additional keys so evaluators do not depend on a moving spec. |
| **OTLP** | Export protocol | **Adopt**. Dev: console exporter + optional OTLP to Langfuse. Prod: OTLP collector. |
| **Langfuse (self-hosted)** | Optional trace UI | **Keep as optional backend**, not the contract. Do not call Langfuse SDK from agents. |
| **LangSmith** | SaaS LangChain tracing | **Do not adopt.** Couples eval/obs to LangChain cloud; duplicates Langfuse. |
| **Prometheus / Grafana** | Metrics dashboards | **Phase 15**, after `record_metric` has real volume. Not Phase 00. |
| **DeepEval** | LLM-as-judge helpers | **Not a dependency.** Optional later for judge implementations behind our `Evaluator` protocol (§L.6). |
| **MLflow** | Experiment tracking | **Not adopted.** Experiments live in Postgres (`evaluation_experiments`, §R) to avoid a second tracking stack. |
| **OpenHands eval harness** | Benchmark methodology | **Borrow ideas only** (fixed tasks, scored diffs, pass@k). Do not import their runner. |

---



# Part C — Implementation Roadmap

Ordered by real dependencies. Cannot build a workflow engine before agents exist; cannot evaluate before real behavior exists.


| Phase                                  | Objective                                                    | Key Deliverables                                                                                                                                        | Dependencies     | Completion Criteria                                                                                                           |
| -------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **0 — Foundations**                    | Safety scaffolding before any agent writes code              | Task model (Pydantic); cost kill-switch; execution sandbox; `TelemetrySink` + OTel adapter; message queue scaffolding; secrets/config management        | None             | Dummy task flows through intake → sandbox → trace log → budget-tracked completion with full audit trail                       |
| **1 — Orchestration Skeleton**         | Working LangGraph graph with durable state and one interrupt | Parent `StateGraph`; PostgreSQL checkpointer; interrupt/resume round-trip                                                                               | Phase 0          | Task paused for approval, process killed, resumes correctly from checkpoint. 100% across 20 crash trials                      |
| **2 — Model Abstraction Layer**        | Model-independence structural from day one                   | `ModelAdapter` interface; GLM adapter; cost tracking callback; pricing registry                                                                         | Phase 0          | Zero provider-specific SDK calls outside `model_adapters/` (grep-verifiable)                                                  |
| **3 — Minimal Repo Intelligence**      | Working retrieval at small scale before scaling              | Tree-sitter symbol index; Zoekt trigram search; git-diff incremental indexing; pgvector store                                                           | Phases 0, 2      | Retrieval precision@5 ≥ 90% on held-out labeled set; incremental update < 10s for 20-file commit                              |
| **4 — Dynamic Requirements Engine**    | Adaptive clarification loop, not a checklist                 | Question bank + predicates; auto-answer-from-repo check; question dependency DAG; confidence-gated exit                                                 | Phase 3          | Asks clarifying questions on ≥ 95% of ambiguous inputs; skips on ≥ 95% of well-specified inputs                               |
| **5 — Planning & Intake Agents**       | Wire Questioning Engine into real intake                     | Planning Manager; intake classifier; Confidence Scorer; `Validator`(phase=requirements)                                                                 | Phase 4          | Confidence score computed and logged on every intake; classification accuracy validated                                       |
| **6 — Design & Implementation Agents** | Design-driven code generation                                | Design Manager + Repo Architecture Analyst; Code Generation sub-agents; parallel fan-out + conflict detection; `Validator`(phase=design,implementation) | Phase 5          | Generated code passes static analysis on first pass ≥ 80% for Low/Medium risk                                                 |
| **7 — Core QA Agents**                 | Incremental QA, impact analysis, bug validation              | Unit/integration test agents; Dependency Impact Agent; Bug Validation Agent; test-impact analysis                                                       | Phase 6          | QA catches ≥ 95% of seeded defects in mutation-tested benchmark                                                               |
| **8 — HITL & Release Governance**      | Real interrupt/resume approval gates + PR flow               | `ApprovalGate` instances at all checkpoints; evidence-bundle generator; PR creation via MCP; auto-merge policy                                          | Phases 1, 7      | Zero agent-authored commits on protected branch without human approval or passing auto-merge check                            |
| **9 — Minimal UI**                     | Orchestration legible to a human                             | 12 screens (§P) as thin read layer over existing backend objects                                                                                        | Phase 8          | Every approval decision made through UI; human can answer "what is running, why, what does it need from me"                   |
| **10 — Workflow Policy Engine**        | Real routing logic as tested code                            | `resolve_workflow_profile()` ordered rule functions; `escalate_model_tier()`; every rule unit-tested                                                    | Phases 5–9       | Routing matches human-architect judgment ≥ 90% on labeled set; every risk×work_type×confidence combination has a passing test |
| **11 — Repo Intelligence at Scale**    | 100k–1M+ files                                               | Federated domain shards; global index-of-indices; NetworkX → Neo4j migration; nightly full-reindex                                                      | Phase 3 proven   | Retrieval precision@5 within 5 points of Phase 3 baseline at 1M-file scale                                                    |
| **12 — Context Engineering**           | Token efficiency without accuracy loss                       | Budget math per phase; AST-boundary chunking; Aider-style PageRank repo map; Phase Handoff Packets                                                      | Phase 11         | Average tokens/task drops ≥ 40% vs. Phase 11 baseline with no drop in task success rate                                       |
| **13 — Advanced QA**                   | Full QA capability stack                                     | Security (Semgrep + CodeQL); performance (k6/Locust); mutation testing; property-based testing; evidence bundles                                        | Phases 7, 10     | Security scan catches ≥ 95% of seeded-vulnerability benchmark                                                                 |
| **14 — MCP & External Integrations**   | Connect to real engineering ecosystem                        | GitHub MCP; Jira MCP; Slack for HITL notifications; adapter pattern for missing servers                                                                 | Phase 8          | End-to-end: task from real ticket → human-approved PR, no manual data re-entry                                                |
| **15 — Evaluation Framework**          | Measure real behavior                                        | `EvaluationEngine` + RunRecord; post-task KPIs; golden dataset; shadow-mode; experiment/baseline CI; DORA                                                                                | Phases 5–14      | Golden-dataset resolution rate is a tracked, trending metric with documented baseline; evaluators do not import LangGraph    |
| **16 — Production Hardening**          | Prove every mitigation works                                 | Second model adapter (zero orchestration changes); induced Postgres HA failover test; queue load test; chaos tests                                      | All prior phases | Every §N risk row has a passing chaos test, not just a design                                                                 |


---



# Part D — LangGraph System Architecture



## D.1 Graph Hierarchy

One Orchestrator Graph per Task, composed of subgraphs matched 1:1 to SDLC phases. Repository Intelligence is a **long-lived shared service**, not a per-task subgraph — its lifecycle (continuously updated, cross-task, federated) doesn't match a task-scoped graph.

```
Orchestrator Graph (per Task)
├── Intake Subgraph
├── Requirements Subgraph
├── Design Subgraph
├── Implementation Subgraph
│   ├── Implementation Manager (decompose + pre-dispatch check, §D.4.2)
│   ├── [Send API → parallel CodeGen instances, isolated worktrees (§D.4.3)]
│   │     each branch: CodeGen → Validator(implementation) [per-branch, tool-only, §D.4.1]
│   ├── Fan-in Coordinator (deterministic, §D.4.1)
│   └── Integration Validator (§E.8 — BaseAgent with tool calls, not a Validator template)
├── QA Subgraph
│   └── [Send API → parallel QA tool runners]
├── Review Subgraph
├── Release Subgraph
└── Monitoring Subgraph

Repository Intelligence Service (shared, federated, never task-scoped)
  └── queried via tool calls from any subgraph
```



## D.2 State & Conditional Routing

One subgraph per phase. The `WorkflowProfile` (§F.1) sets a flag per node (`active | skipped | parallel_eligible`) consumed by conditional edges *inside* that single subgraph. **Not** maintained as multiple subgraph variants — same flexibility, one fewer moving part.

### D.2.1 Task ↔ Graph Phase Synchronization

`Task.state` (§B.1, Postgres `tasks.state`) is the **durable source of truth** for which SDLC phase a task is in. `SDLCState` does **not** carry a `task_state` field — graph position is tracked via `Task.state` plus LangGraph checkpoint state.

| Event | Who updates | What is written |
|---|---|---|
| Graph node entry (phase transition) | The entering node's wrapper (shared middleware or each phase Manager's entry hook) | `update_task_state(task_id, TaskState.<phase>)` via `task_repository` |
| Feedback-loop backward edge | The routing node that fires the backward edge | `Task.state` set to the reentry phase (§D.3 rollback table) |
| Task completion | Terminal node (`monitoring` exit or `done` handler) | `TaskState.DONE` |
| Kill-switch / budget exceeded | Kill-switch handler | `TaskState.BLOCKED` |
| Task cancellation | Cancellation handler (§D.9.9) | `Task.state` preserved as last active phase; cancellation reason stored on Task/checkpoint |

**UI synchronization:** Screen 4 (§P) reads `Task.state` for current phase and derives transition history from `agent_events` (observability only — never used for routing). `GET /tasks/{id}/phase-history` returns ordered transitions including backward edges.

**Graph synchronization:** LangGraph checkpoint holds in-flight `SDLCState`; `Task.state` is updated at node boundaries so restarts and UI queries agree without reading checkpoint internals.

## D.3 Phase State Machine

```
intake → requirements → design → implementation → qa → review → release → monitoring → done

Backward edges (explicit, not implicit):
  QA fail → implementation  (default)
  QA flags design defect → design (HITL required)
  Review changes-requested → implementation
  Design validator flags requirement gap → requirements (HITL required)
  Monitoring incident → new Task (linked via lineage), NOT back to original graph
```

**Rollback precision (§2.5 from V2, kept and extended):**


| Failure                            | Reentry Point                    | Max Depth | HITL        |
| ---------------------------------- | -------------------------------- | --------- | ----------- |
| Requirements Validator             | Clarification node (same phase)  | Unlimited | No          |
| Design Validator — design gap      | System Architect node            | 5×        | No          |
| Design Validator — requirement gap | Requirements phase               | 1×        | Yes         |
| Code Review / static fail          | Implementation Agent (same task) | 3×        | No          |
| Integration Validator              | Implementation Manager           | 2×        | No          |
| QA — spec compliance fail          | Implementation phase             | 3×        | No          |
| QA — design defect                 | Design phase                     | 1×        | Yes         |
| QA — critical security finding     | Design phase                     | 1×        | Yes         |
| Deployment health fail             | CI/CD rollback (automated)       | Auto      | No          |
| Confidence below floor (any phase) | Previous checkpoint              | 1×        | Yes         |
| MASC critical anomaly              | Previous phase checkpoint        | 1×        | Yes         |
| `rollback_count ≥ max`             | Suspend task, preserve state     | —         | Yes (force) |




## D.4 Parallel Execution & Conflict Handling

Fan-out via `Send` API for: independent implementation sub-tasks, parallel QA tool runners, embedding generation.

### D.4.0 Canonical Implementation Subgraph Order

Every document describing the implementation phase MUST use this exact sequence:

```
Implementation Manager
  → Send fan-out (one branch per sub-task in each parallel group)
       Per branch (isolated worktree, §D.4.3):
         1. CodeGen Sub-agent → diff + WorkerCoordinationPacket (Blackboard refs)
         2. Validator(implementation) [static-analysis, tool-only, independent of CodeGen]
              ├─ pass → append ImplementationResult(status="validated") — branch eligible for fan-in
              └─ fail → FL-04 → FeedbackReport → retry CodeGen (same subtask_id, attempt_number++)
                        └─ 3× fail on same module → Feedback Agent → HITL if still failing
  → Fan-in Coordinator (§D.4.1) — all branches in the parallel group complete or blocked
  → Integration Validator (merged diff set)
       └─ fail → FL-05 → Implementation Manager (re-assign, max 2×)
```

**Key invariant:** `Validator(implementation)` runs **per branch, before Fan-in** — never on the merged result. Only branches with `ImplementationResult.status="validated"` enter merge eligibility. `FL-04` targets the originating CodeGen sub-agent because validation is per-diff, not post-merge.

### D.4.1 Fan-in Coordinator (deterministic, not an agent)

Every fan-out (`Send`) is closed by a **Fan-in Coordinator** graph node. This is explicitly **not an LLM call, not an agent, and not a reasoning component** — it is a deterministic function over branch outputs and their `WorkerCoordinationPacket`s (§D.9.2). Its job is to decide, by rule, what happens next; it never generates or resolves code itself.

**Input scope:** Fan-in runs only after every branch in the parallel group has either (a) produced an `ImplementationResult` with `status="validated"`, or (b) stopped with `status="blocked"` and a `ClarificationEscalation`. Branches mid-FL-04 retry do not trigger fan-in — LangGraph keeps the branch open until validation passes or exhausts.

**Decisions the Fan-in Coordinator performs, in order:**

1. **WCP selection** — for each `subtask_id`, consider only the `WorkerCoordinationPacket` with the highest `attempt_number` (superseded WCPs from prior attempts are ignored, not deleted).
2. **Overlap detection** — computes the file set touched by each validated branch (`WorkerCoordinationPacket.touches_files`, cross-checked against `ImplementationResult.touches_files` and the actual diff from Blackboard) and flags any pairwise overlap.
3. **Semantic conflict detection (WCP-based, deterministic)** — independent of file overlap, applies the rules in §D.4.1.1.
4. **Merge eligibility** — validated branches with no file overlap and no flagged semantic conflict are merged into the integration worktree (§D.4.3).
5. **Serialization** — overlapping branches (by file or by flagged semantic conflict) are discarded and re-dispatched *sequentially* per §D.4.4 — never silently auto-merged.
6. **Replanning trigger** — if any `WorkerCoordinationPacket.needs_manager_attention` is set, or a `ClarificationEscalation` was raised (§D.9.3) by any branch, the Coordinator batches these and routes to the Implementation Manager for a bounded replan (§D.9.6) *before* proceeding to Integration Validator — capped at one replan per parallel group per attempt.
7. **Integration Validator triggering** — once merge/serialization/replan resolve cleanly, dispatch to `Integration Validator`.

#### D.4.1.1 WCP Semantic-Conflict Matching Rules (v1, deterministic, no LLM)

For each unordered pair of branches `(A, B)` where both have `status="validated"`:

1. **Symbol normalization:** every `interface_changes[].symbol` and every token extracted from `assumptions`/`discovered_dependencies` is normalized to RI `symbol_id` format: `{file_path}::{qualified_name}` (§G.6.1). Strip whitespace; lowercase file paths; leave qualified names case-sensitive.
2. **Direct symbol match:** conflict if any `A.interface_changes[].symbol` equals any entry in `B.assumptions` or `B.discovered_dependencies` after normalization, OR vice versa.
3. **Substring fallback (assumptions only):** if step 2 finds no match, conflict if any normalized `A.interface_changes[].symbol` appears as a substring in any normalized `B.assumptions` string (or vice versa). Do **not** apply substring matching to `discovered_dependencies` — exact symbol_id match only for that field.
4. **RI caller cross-check:** for each `interface_changes[].symbol` in branch A, call `get_callers(symbol, depth=1)`. Conflict if any caller's `symbol_id` appears in branch B's `assumptions` or `discovered_dependencies` (normalized exact match).
5. **Parse failure → Fail-Closed:** if any WCP field required for steps 1–4 is missing or fails schema validation, set `needs_manager_attention=true` on that WCP and route to Manager replan (step 6 above) — never silently treat as non-conflicting.
6. **RI unavailable during cross-check:** if step 4's RI call fails or times out, treat as conflict (Fail-Closed) and flag for serialize-and-rerun or Manager replan — never assume no conflict.

Overlapping/conflicting branches are **never** silently merged — this correctness-over-throughput stance is unchanged from earlier revisions of this document, now made precise by having the Coordinator's exact decision list written down instead of left to "the fan-in node checks for overlaps."

**File-level overlap detection is the v1 granularity, by design** — it is the simplest mechanism that is never *wrong in the unsafe direction* (it may over-trigger a re-run on two agents editing unrelated parts of the same large file, but it will never miss a real conflict the way naive line-level diffing could). Finer-grained detection is future roadmap only, not v1:

- **Symbol-level overlap** (two branches touch different functions in the same file — currently treated as a conflict at file granularity) — revisit once real conflict-rate data (Phase 15's loop-trigger-rate KPI) shows file-level granularity is a genuine throughput problem, not before.
- **AST-level / semantic dependency-graph overlap detection** (beyond the WCP-based interface-change check in decision 2 above) — a research-track item, not scheduled into any v1 phase.
- **Any LLM-assisted "predict likely conflicts before dispatch" mechanism** — evaluated and deferred; the deterministic post-hoc check above is cheaper and more auditable than a predictive model that could be wrong in either direction.

At high task volume, concurrent graphs hit shared Repository Intelligence stores. Mitigation: read/write separation (incremental-indexing writes → primary; agent-execution reads → replicas).

### D.4.2 Pre-dispatch Overlap Check (deterministic, Manager-owned)

Before the Implementation Manager calls `Send()` for any parallel group, it **may** run one lightweight, deterministic validation — no LLM call, no prediction, no new agent. This is an optimization only; the Fan-in Coordinator (§D.4.1) remains the **final authority** for overlap and conflict detection after workers complete.

The Manager compares, using Repository Intelligence and the proposed `TaskDecomposition`:

- `ownership_map` — which sub-task claims which module/file scope
- planned file sets per sub-task (from decomposition + RI file index lookups)
- dependency graph consistency (`get_dependencies` / `get_dependents`)

If obvious file-level overlap is detected among sub-tasks scheduled to run in the **same parallel group**, the Manager adjusts decomposition **before dispatch** — typically by merging overlapping sub-tasks or moving one to a later sequential group. If no overlap is found, dispatch proceeds unchanged.

This check never replaces Fan-in validation. Workers may still touch files outside their assigned scope during execution; Fan-in + WCP semantic-conflict detection catches that. The pre-dispatch check only reduces avoidable fan-out/re-run cycles when overlap is already visible in the plan.

### D.4.3 Git Isolation Contract

Minimal, binding rules for parallel CodeGen and Fan-in merge. No new agents — enforced by sandbox + worktree permissions.

| Concept | Convention |
|---|---|
| **Base commit** | `task_base_sha` — repo HEAD at Implementation Manager dispatch time; immutable for the task attempt |
| **Per-branch worktree** | `{repo_root}/.sdlc/worktrees/{task_id}/{subtask_id}/` on branch `sdlc/{task_id}/{subtask_id}` |
| **Integration worktree** | `{repo_root}/.sdlc/worktrees/{task_id}/integration/` on branch `sdlc/{task_id}/integration` |
| **Branch naming** | `sdlc/{task_id}/{subtask_id}` for workers; `sdlc/{task_id}/integration` for merged result |
| **Allowed writers** | CodeGen sub-agent → its own per-branch worktree only. Fan-in Coordinator → integration worktree only. No other component writes git state during implementation. |
| **Merge authority** | Only Fan-in Coordinator applies validated branch diffs into the integration worktree. Workers never merge into integration or sibling worktrees. |
| **Serialize-and-rerun replay** | On serialization (§D.4.4): discard affected branch worktrees, recreate from `task_base_sha`, re-dispatch sequentially — second branch's worktree is created **after** first branch's diff is applied to integration, then branched from integration HEAD so it sees the first branch's applied change. |
| **Cleanup** | Remove all `{task_id}` worktrees/branches on: successful Implementation phase exit, task cancellation (§D.9.9), or task completion. Partial cleanup on fan-in merge success is allowed but full task cleanup is mandatory at phase exit. |

**Blackboard pointer format (all services):** `{task_id}/{kind}/{uuid}` — e.g. `abc123/diff/7f3a…`. Returned by `BlackboardService.store()`; accepted by `retrieve()` and `exists()`.

### D.4.4 Serialize-and-Rerun LangGraph Flow

When Fan-in decision 5 (serialization) fires:

1. Fan-in Coordinator marks the conflicting `ImplementationResult` entries as superseded (new attempt will produce fresh entries).
2. Returns `Command(goto="codegen_sequential_redispatch")` — **not** a new `Send` fan-out. The conflicting sub-tasks run as ordinary sequential graph nodes (group size = 1), in dependency order determined by the Manager.
3. Each redispatched sub-task increments `attempt_number`; idempotency checks (§D.9.8) key on `(task_id, subtask_id, attempt_number)`.
4. Each redispatched branch repeats the full per-branch path: CodeGen → Validator(implementation) → append new `ImplementationResult`.
5. After all serialized branches complete validation, Fan-in Coordinator **re-runs** decisions 1–7 on the new result set — it does not proceed to Integration Validator until the serialized group is conflict-free or escalates via replan/HITL.
6. Manager interaction: if serialization alone cannot resolve (e.g. circular semantic dependency), Fan-in triggers the bounded Manager replan (§D.9.6) with assembled `ReplanContext` before a third fan-out attempt.

## D.5 Retry & Failure Routing

Per-node `retry_policy` (LangGraph native) with exponential backoff; max attempts from `Task.budget.max_retries_per_node`. After retry exhaustion:

1. Route to Feedback Agent (synthesizes correction from failure history).
2. If Feedback Agent's revised approach still fails → human escalation (Fail-Closed, Principle 8).

**Workers must be idempotent (§D.9.8).** Retries, checkpoint replay, and interrupt/resume must never produce duplicate side effects (double commits, double sandbox runs, duplicate WCP entries for the same completed subtask). LangGraph may re-enter a node; the worker's responsibility is to detect prior completion for its `subtask_id` and exit cleanly rather than repeat work.

**Replanning is never reasoning from a blank slate.** Any node that triggers a replan (Feedback Agent, `FL-05` re-assignment, or the Fan-in Coordinator's replan trigger above) constructs a `ReplanContext` (§B.2) from the task's accumulated `feedback_reports`, `worker_coordination_packets`, and `clarification_escalations`, and hands it to the responsible Manager alongside the new instructions. `attempt_number` (§D.8) is only meaningful because `ReplanContext` makes each attempt strictly more informed than the last — without it, a "3rd attempt" would just be the 1st attempt run three times.



## D.6 Code Rollback vs. Orchestration Rollback (Kept Separate)


| Concern                          | Mechanism                                           |
| -------------------------------- | --------------------------------------------------- |
| **Code rollback**                | Git branch per task; revert = discard/revert branch |
| **Orchestration-state rollback** | LangGraph checkpoint replay from any prior step     |


Never conflate these. LangGraph checkpoints are for debugging and resuming the process, not for undoing code.

## D.7 Human Approval Nodes

`interrupt()` calls immediately before irreversible transitions (design approval, release, deployment). Rendered via `ApprovalGate` template (§E.1). Resume via `Command(resume=...)`. Rendered concretely in §P.

Every human-facing pause is a `HITLRequest` (§B.2) with an explicit `request_type` discriminant — `clarification` (open requirements question, Requirements Analyst), `approval` (an `ApprovalGate` checkpoint — scope/design/pr/deployment), `policy_review` (a `WorkflowProfile` rule requires human sign-off on a routing decision itself, not on task content), or `risk_approval` (a Critical-risk-tier escalation that doesn't map to a normal checkpoint, e.g. a Feedback Agent's second failed revision). This is what Screen 7 vs. Screen 8 (§P) and RBAC filtering (§S) key off — there is no separate implicit "type" convention layered on top of the schema.

### D.7.1 HITL Queue Lifecycle (`hitl_queue` vs `hitl_log`)

Two layers serve different purposes; **Postgres `hitl_log` is the durable source of truth** across process restarts.

| Layer | Location | Purpose | Lifecycle |
|---|---|---|---|
| **`hitl_log`** | Postgres (§R) | Durable audit + UI query source | Row created on `interrupt()`; updated on response/timeout |
| **`SDLCState.hitl_queue`** | In-graph working set | Pending requests visible to the running graph | Appended on interrupt; entry removed on resume |
| **`SDLCState.hitl_history`** | In-graph append-only log | Completed HITL for this task session | Appended on resume with full `HITLRequest` including response |

**On `interrupt()` (any HITL type):**
1. Build `HITLRequest` with `request_type` set explicitly (never implicit).
2. Insert row into `hitl_log` (`request_type`, `phase`, `reason`, `evidence_ref`, `options`, `timeout_at`; `responded_at` NULL).
3. Append the same request to `SDLCState.hitl_queue`.
4. Call LangGraph `interrupt()` with the request payload.

**On resume (`Command(resume=...)`):**
1. Update `hitl_log` row: `response`, `responded_by`, `responded_at`.
2. Remove matching entry from `SDLCState.hitl_queue`.
3. Append completed request to `SDLCState.hitl_history` (`append_only`).
4. Route based on decision (ApprovalGate template, Requirements Analyst, etc.).

**On timeout (Fail-Closed):** scheduled job checks `hitl_log.timeout_at`; on expiry, escalate (hold/notify) — never auto-approve. Update `hitl_log` with escalation status; clear from `hitl_queue`; do not append to `hitl_history` as approved.

**UI/API reads:** `list_pending_hitl()` queries `hitl_log WHERE responded_at IS NULL` — not `SDLCState.hitl_queue` — so pending items survive worker restarts.

## D.8 Feedback Reports vs. Clarification Escalations (Structured, Never Bare)

Two distinct failure/uncertainty signals exist, and the architecture deliberately keeps them separate rather than merging them into one generic "problem" object:

| | `FeedbackReport` | `ClarificationEscalation` (§B.2) |
|---|---|---|
| **When raised** | *After* a Validator/MASC/QA check rejects a completed output | *Before* a worker completes — it cannot safely finish at all |
| **Who raises it** | `Validator`, MASC, QA agents | The worker itself (CodeGen sub-agent, or any future parallel worker) |
| **Contains** | What was wrong with a finished artifact | What is unknown, or which assumption broke, mid-work |
| **Routes to** | The producing agent (retry) or, on exhaustion, Feedback Agent | The Fan-in Coordinator → Implementation Manager (batched), never another worker |
| **Never** | A bare "try again" | A silent guess in place of the missing information |

Every feedback loop carries a `FeedbackReport`:

```python
class FeedbackReport(TypedDict):
    loop_id: str                # e.g., "QA_to_Implementation"
    failed_agent: str
    failure_type: str
    validator_findings: list[dict]
    specific_gaps: list[str]    # What exactly to fix, not "try again"
    suggested_approach: str | None
    attempt_number: int
```

Agents receive structured findings, not bare retry signals. `ClarificationEscalation`'s schema is defined in §B.2, alongside `WorkerCoordinationPacket` and `ReplanContext` — all three exist for the same reason `FeedbackReport` does: structured, typed communication instead of free-form text passed between graph nodes.

## D.9 Agent Communication Architecture

### D.9.1 The Communication Invariant

**Workers never communicate directly with other workers. Peer-to-peer agent messaging is architecturally forbidden — not merely undocumented.** This is Principle 9 (§A.2) made operational: parallel workers remain intentionally unaware of siblings; cross-branch knowledge is assembled only at Fan-in.

All coordination between concurrently-running units of work happens exclusively through one of:

- **The Phase Manager** that dispatched them (decomposition, replanning, redispatch)
- **The Fan-in Coordinator** (§D.4.1) — deterministic, not an agent
- **`SDLCState`** — shared, reducer-governed graph state
- **The Blackboard** (§D.9.4) — pointer-referenced artifact store
- **Repository Intelligence** (§G) — shared, read-mostly service
- **HITL** (§D.7) — only for requirement/scope/business/policy ambiguity, never for "what does another agent's output mean"

A worker that needs something from another worker's output waits for fan-in and reads the result from `SDLCState`/blackboard — it does not, and structurally cannot, message that worker directly. This is also the project's deadlock-prevention strategy: because no worker ever waits *on another worker*, worker-to-worker circular waits are not a reachable state. The only waits are worker→Manager/HITL (never circular, since Managers and HITL do not wait on workers they dispatched) and standard node retry/timeout (§D.5, §E.1).

**Explicitly rejected as violations of this invariant (see §D.9.7 for the full list):** direct worker↔worker messaging, swarm/emergent multi-agent coordination, always-on multi-agent "meeting" rounds, an LLM-driven Merge Resolution Agent negotiating conflicting diffs, recursive worker spawning, and using the `messages` field (§B.2) as an inter-agent bus.

### D.9.2 Worker Coordination Packet (WCP)

Every parallel worker (currently: CodeGen sub-agents, §E.8; any future `Send`-dispatched worker inherits this contract) emits a `WorkerCoordinationPacket` (schema in §B.2) on branch exit, whether it completed or stopped itself via `ClarificationEscalation`.

| Property | Value |
|---|---|
| **Producer** | The worker itself, as part of its normal completion output |
| **Consumer** | Fan-in Coordinator (§D.4.1); Implementation Manager on replan (via `ReplanContext`) |
| **Lifecycle** | One WCP per worker per dispatch; appended to `SDLCState.worker_coordination_packets` (`append_only`); superseded (not deleted) on redispatch — Fan-in considers only the highest `attempt_number` WCP per `subtask_id` (§D.4.1 step 1) |
| **Storage** | Small structured fields inline in `SDLCState`; `artifact_refs` field points to the Blackboard for the actual diff/logs |
| **Validation** | Schema-validated the same way any agent output is (MASC Check 1, §E.6) — a malformed WCP is treated as `needs_manager_attention=true` (Fail-Closed), never silently dropped |
| **Token cost** | Designed to be produced as structured-output fields of the *same* model call that produces the worker's diff — not a second LLM round-trip. A worker only needs a second call if its first output's WCP fields are incomplete, which MASC's schema check catches |
| **Relationship to Fan-in** | Primary input to Coordinator decisions 1–2–5 (§D.4.1) |
| **Relationship to Validators** | Independent of `Validator`(implementation) and Integration Validator — a WCP reports the worker's own beliefs; it is not itself a validation result |
| **Relationship to Replanning** | Aggregated into `ReplanContext.wcp_summaries` (§B.2) so a Manager replanning after a flagged WCP sees exactly what was discovered, not a re-summary |

**Minimum-information principle:** the WCP schema (§B.2) intentionally excludes free-text "notes" or "reasoning" fields beyond `risks`/`assumptions` as short strings — anything longer belongs on the Blackboard via `artifact_refs`, keeping the packet itself cheap to read at fan-in.

### D.9.3 Clarification Escalation Protocol

The largest gap identified in the pre-implementation communication audit — "what happens when a worker discovers its assumptions are wrong mid-task" — is closed by this protocol, not by opening a channel to another agent.

```
Worker blocked or assumption invalidated
        │
        ▼
Repository Intelligence consulted (always first — cheapest, no peer/human cost)
        │
   still blocked?
        │ yes
        ▼
Worker emits ClarificationEscalation (§B.2), sets WorkerCoordinationPacket.blocked=true,
stops its own branch (does not guess; Fail-Closed) — sibling branches are unaffected and continue
        │
        ▼
Fan-in Coordinator batches all escalations from the parallel group (D.4.1 decision 5)
        │
        ▼
Implementation Manager reasons over the batch using ArchitectureDoc + RI + ReplanContext
        │
   ┌────┴─────────────────────────┐
   │ resolvable from design + RI  │  scope/requirement/business/policy ambiguity
   ▼                              ▼
Redispatch affected worker(s)     HITL (request_type=clarification or policy_review)
with revised instructions         → resume → redispatch
```

**Rules:**

- **Repository Intelligence first, always** — `ClarificationEscalation.ri_consulted` must be `true` except for pure scope-ambiguity cases where no repo query could possibly answer the question.
- **Batched, not streamed** — the Manager resolves a whole parallel group's escalations in at most one reasoning pass per batch, not one call per escalation.
- **A worker never resumes itself** — resolution always comes from the Manager (redispatch) or HITL→Manager; there is no worker↔worker "here's the answer" path.
- **HITL is the exception, not the default path** — reached only when the Manager cannot resolve the escalation from documents it already has authority over (`ArchitectureDoc`, `RequirementsSpec`, RI). Escalations about "which helper function already exists" are RI questions, not HITL questions.
- **Interaction with Feedback Loops:** an unresolved `ClarificationEscalation` is not itself a `FeedbackReport` — it precedes completion, a `FeedbackReport` follows a completed-but-rejected output (§D.8's table). If redispatch after clarification still fails validation, the *normal* `FL-04`/Feedback Agent path applies from there.
- **Interaction with Replanning:** unresolved escalations feed `ReplanContext.unresolved_clarifications` (§B.2) so a later replan doesn't re-ask a question already answered.

### D.9.4 Blackboard — Minimal Service, Available from Phase 6

The blackboard principle (large payloads referenced by pointer, never inlined into graph state) is unchanged from earlier revisions of this document. What changes here: **a minimal Blackboard service must exist by the time Implementation (Phase 6) first produces real diffs — it is not deferred until the Evidence Bundle work in Phase 8.** Phase 8 is free to *enrich* the service (evidence bundle assembly, richer indexing); it does not *originate* it.

Minimum API (deliberately small — do not over-engineer ahead of real usage):

```python
class BlackboardService(Protocol):
    def store(self, task_id: str, kind: str, content: bytes | dict) -> str: ...   # returns a pointer ref
    def retrieve(self, ref: str) -> bytes | dict: ...
    def exists(self, ref: str) -> bool: ...
```

A content-addressed or task-scoped Postgres JSONB/table-backed implementation is sufficient at this scale; dedicated object storage is a future-scale concern (see §G.4's federation discussion for the analogous "don't pre-split for scale you don't have yet" reasoning), not something to build ahead of need.

**No separate `BlackboardArtifactRef` wrapper type is introduced.** Every pointer in this document is already a plain `str` field (`evidence_ref`, `artifact_refs`, `artifact_ref`) that `BlackboardService.retrieve()` accepts directly. Format: `{task_id}/{kind}/{uuid}` (§D.4.3). A typed wrapper class would add an object without adding capability — rejected under the "avoid unnecessary objects" constraint.

**Failure contracts (Fail-Closed):**

| Failure | Behavior |
|---|---|
| `store()` fails | Worker branch → `ClarificationEscalation(category="missing_context")`, `blocked=true`, stop — never proceed without persisted artifact |
| `retrieve()` fails / ref missing | Treat as missing artifact → same escalation path; Manager/Fan-in may retry retrieve once, then escalate |
| `exists()` returns false for required ref | Fail-Closed — do not substitute empty content |

## D.9.5 Manager Authority (Who May Spawn, Reassign, Replan)

Explicit, project-wide, not per-phase:

| May do | Manager | Worker |
|---|---|---|
| Decompose work into sub-tasks | ✅ | ❌ |
| Dispatch (`Send`) workers | ✅ | ❌ |
| Redistribute/reassign work between workers | ✅ | ❌ |
| Trigger a replan | ✅ | ❌ |
| Spawn additional workers (recursively) | ❌ (not needed — see §D.9.7) | ❌ |
| Coordinate directly with another worker | ❌ (Managers coordinate via state/redispatch, not "chat") | ❌ |

Only a Manager (Implementation Manager for the implementation phase; the analogous phase Manager elsewhere) holds `Send` authority. A worker that discovers it needs help does not delegate or reassign anything — it raises a `ClarificationEscalation` and stops; only the Manager redispatches. This keeps `max_parallel_impl_agents` (§F.2) and cost budgets meaningful — an uncontrolled worker-spawns-worker path would make both unenforceable.

### D.9.6 Conditional Coordination (No Always-On Meetings)

Coordination beyond the default isolated-worker → fan-in path happens **only when triggered**, never on a fixed schedule or "just in case":

| Trigger | Resulting coordination |
|---|---|
| A `WorkerCoordinationPacket.needs_manager_attention = true` | Fan-in Coordinator batches it into a bounded Manager replan |
| One or more `ClarificationEscalation`s in a parallel group | Same batched Manager pass (§D.9.3) |
| Neither of the above | **No coordination step runs at all** — straight to merge/Integration Validator |

**Bound:** at most **one** Manager coordination/replan pass per parallel group per attempt. If that pass's redispatch still fails validation, the task proceeds through the normal `FL-04`/`FL-05`/Feedback Agent escalation chain (§D.5, §D.8) rather than triggering a second ad-hoc coordination round. A dedicated "coordination window" phase between decomposition and implementation, or between implementation and merge, that runs unconditionally on every task was evaluated and rejected (§D.9.7) — it taxes every Low-risk task with LLM rounds that, empirically, most tasks never need.

### D.9.7 Communication Non-Goals (Reject on Sight)

The following are explicitly out of scope for this architecture. Naming them here is deliberate — to prevent future architectural drift toward "just this once" exceptions:

- **Worker ↔ worker communication of any kind**, direct or relayed through a shared mutable object they both poll.
- **Swarm or emergent multi-agent coordination** for any core SDLC workflow (see the platform's own decentralized-patterns evaluation — swarm/peer-to-peer/voting/auction/full consensus were assessed and rejected for the control plane).
- **Debate architectures as a default mechanism.** (Bounded, opt-in design-debate for Critical/High-risk design exploration remains a *separate*, policy-gated research track — it is not part of this communication protocol and does not relax the worker-isolation invariant.)
- **Always-on coordination meetings/windows** that run unconditionally on every task (§D.9.6).
- **Recursive worker spawning** — only Managers hold `Send` authority (§D.9.5).
- **An LLM-driven Merge Resolution Agent** that creatively resolves conflicting diffs. Merge conflicts are handled deterministically by the Fan-in Coordinator (overlap/semantic-conflict detection → serialize-and-rerun), never by asking a model to reconcile two diffs into one. This is a correctness and auditability decision, not an oversight: an auto-merged "creative" resolution is exactly the kind of silent, unverifiable change Principle 5 (deterministic/auditable over clever) exists to prevent.
- **Using `messages` (§B.2) as an inter-agent bus.** It is the human/system conversation transcript only (§B.2's field comment) — agent coordination has its own typed channels (`worker_coordination_packets`, `clarification_escalations`, `feedback_reports`).

### D.9.8 Worker Lifecycle

```
Created (Send dispatch from Manager)
   │
   ▼
Running (progressive RI context, sandboxed diff generation in isolated worktree, §D.4.3)
   │
   ├──▶ Diff produced ──▶ Validator(implementation) [per-branch, tool-only, §D.4.0]
   │         │
   │         ├──▶ pass ──▶ ImplementationResult(status="validated") + WCP ──▶ eligible for Fan-in
   │         │
   │         └──▶ fail ──▶ FL-04 → FeedbackReport → retry CodeGen (attempt_number++)
   │                        └─ 3× fail → Feedback Agent → HITL
   │
   ├──▶ Blocked (mid-work) ──▶ ClarificationEscalation + WCP(blocked=true) + ImplementationResult(status="blocked") ──▶ Fan-in batch
   │                    │
   │                    ▼
   │              Manager resolves (RI/design) or HITL ──▶ Redispatch ──▶ Running (new attempt)
   │
   ├──▶ Cancelled (task-level cancellation, §D.9.9) ──▶ worktree/branch cleanup, no merge
   │
   └──▶ Failed (unrecoverable) ──▶ ImplementationResult(status="failed")
```

A worker's branch is always in exactly one of these states; there is no "waiting on another worker" state, by construction (§D.9.1).

**Idempotent worker contract (production requirement).** Every implementation worker (CodeGen sub-agent and any future `Send`-dispatched worker) must safely tolerate retries, interrupt/resume, checkpoint recovery, and duplicate execution requests without performing duplicate side effects. This is implementation-agnostic — the contract is behavioral, not a specific storage mechanism:

- **Subtask identity:** every execution is keyed to `(task_id, subtask_id, attempt_number)`. The worker checks whether this subtask already has a completed result in `SDLCState`/`Blackboard` before repeating sandbox writes or git mutations.
- **Completed work detection:** if a prior attempt for the same `subtask_id` already produced a valid diff + WCP, the worker returns that result rather than regenerating — unless the Manager explicitly redispatched with revised instructions (new attempt).
- **Safe retries:** a retried node re-executes only the failed step; it does not append duplicate artifacts, duplicate git commits, or duplicate WCP entries for the same successful partial work.
- **Checkpoint recovery:** after process crash and resume, LangGraph may replay from the last checkpoint. The worker must not assume it is the first execution — it must consult existing branch state (worktree, blackboard refs) before acting.
- **Same final result:** duplicate execution of an idempotent worker for the same inputs must converge to the same observable outcome (same diff content or same blocked/escalation signal), not fork the task into inconsistent parallel realities.

Violating idempotency breaks fan-in correctness, cost accounting, and audit trails — treat it as a P0 implementation bug, not an optimization.

### D.9.9 Cancellation & Cleanup

Task cancellation (human-initiated, or budget/kill-switch-triggered per §B.7) follows a defined sequence rather than being left as an implicit "the graph just stops":

```
Task Cancel requested
   │
   ▼
Abort graph execution (no further node dispatch; in-flight LLM calls allowed to finish, not killed mid-token)
   │
   ▼
Signal all in-flight worker branches to stop (no new tool calls dispatched)
   │
   ▼
Clean up task-scoped git worktrees/branches (§E.8's CodeGen isolation mechanism) and any sandbox containers
   │
   ▼
Write a final checkpoint recording state="cancelled" and the cancellation reason
   │
   ▼
Persist final `Task` record (state, partial artifacts, cost-to-date) — nothing silently discarded
```

Cancellation is orthogonal to code rollback (§D.6) — cancelling a task does not revert already-merged code; it stops further orchestration. If already-merged code must be reverted, that is a separate, human-initiated code rollback action.

---



# Part E — Agent Architecture



## E.1 Agent Templates (Two Patterns, Config-Parametrized)

All "approval" and "validation" roles are instances of two templates. This eliminates the bespoke-class explosion while maintaining **full independence**: each template instance is its own graph node, evaluated independently of the producing agent.

```yaml
ApprovalGate:           # replaces N bespoke approval-agent classes
  checkpoint: enum[scope, design, security, release, pr, deployment]
  evidence_bundle_spec: ref          # what's shown: diff, QA results, confidence breakdown, precedent tasks
  applies_when: <rule from §F.3>    # which risk tier / confidence band triggers this gate
  decision_options: [approve, reject_with_feedback, request_changes]
  timeout_minutes: int               # Fail-Closed: if timeout expires → escalate, never auto-approve

Validator:              # replaces N bespoke validator-agent classes
  phase: enum[requirements, design, implementation, qa]
  rule_set: ref         # consistency-checker | design-checklist | static-analysis | qa-plan-compliance
  independent_of: <producing_agent>  # structurally enforced
  on_failure: enum[feedback_loop, hitl, suspend]
```



## E.2 Agent Granularity Principles

- **One Manager per SDLC phase** for coordination and as the graph's boundary.
- **Sub-agents only where tool or context requirements genuinely differ.** Security QA needs different tools than Unit Test — real split. Two agents processing different files is parallelism (fan-out), not a split.
- **Validators are always separate from the producing agent.**
- **Human approval agents only at genuinely irreversible or high-blast-radius transitions.**
- **Feedback Agent** is a named, distinct role — what happens after N consecutive failures on the same module (see §E.5).
- **Only Managers spawn/reassign/replan work (§D.9.5).** A sub-agent that discovers it needs help raises a `ClarificationEscalation` (§D.9.3) and stops its own branch — it never spawns a helper worker, delegates to a peer, or reassigns scope itself. This is the same anti-sprawl discipline as the template rule above, applied to coordination authority rather than to class proliferation.



## E.3 Agent Specialization Techniques

Beyond system prompts, these techniques measurably improve agent reliability. Recommended where cost/complexity is justified.

### Structured Reasoning Patterns


| Technique                                          | When to Use                                                  | Implementation                                                                                                                                          |
| -------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ReAct (Reason + Act)**                           | All implementation and retrieval agents                      | Standard; already native to LangGraph tool-calling nodes                                                                                                |
| **Chain-of-Thought**                               | Design agents, Security Architect, Confidence Scorer         | Prefix output schema with `reasoning: str` field that the agent must populate before conclusions                                                        |
| **Planner-Executor split**                         | Implementation Manager → CodeGen sub-agents                  | Manager plans (high-capability model); Executors implement (cheaper model). Already in architecture                                                     |
| **Reflection / Self-Critique**                     | Requirements Architect after drafting spec; Design Validator | Add a second LLM call: "Review your answer for gaps or contradictions before finalizing." Only for high-stakes outputs — adds cost                      |
| **Multi-step validation (Validator-of-Validator)** | Critical security design, production migration               | `Validator`(design) → MASC check on validator's output. Prevents a validator failing silently                                                           |
| **Structured output schemas**                      | All agents                                                   | Every agent output is a Pydantic schema defined in `agents/prompts/schemas/`. MASC Check 1 validates against this schema before any output enters state |




### Specialized Tools (Restricts Scope Intentionally)

- Each agent receives only the tools its role requires. A Code Review Agent does not receive code-write tools. An Implementation Agent does not receive deployment tools.
- Tool access is defined in agent config, enforced at the LangGraph node level, not by prompt instruction.



### Specialized Retrieval

- **Requirements Architect:** semantic search over historical requirements + similar task episodic memory. Does not receive raw codebase access.
- **Design Manager:** structural graph queries (architecture, component relationships, ADRs). Semantic search for similar past designs.
- **CodeGen Sub-agents:** progressive context expansion tools only (symbol signatures → bodies on demand). Bounded context budget (§H.2).
- **Security Architect:** STRIDE threat model prompt; retrieval scoped to security patterns and historical security findings only.
- **QA agents:** access to test history, regression history, and diff. No access to broader codebase.



### When Fine-Tuning Is Justified

Fine-tuning is high-cost to maintain and not justified for most agents. It is justified when:

1. **High-volume, narrow-task agents** with well-defined I/O: e.g., Intent Drift Classifier (classifies each new user message as ADDITIVE/MODIFICATION/CONTRADICTION). Thousands of examples exist; the task is well-bounded.
2. **Output format compliance** where few-shot prompting consistently fails: if a CodeGen sub-agent repeatedly fails to produce valid diffs in the expected format despite schema enforcement, fine-tuning on format is cheaper than repeated validation loops.
3. **Domain-specific security reasoning**: if the organization has a corpus of security findings specific to their stack, a fine-tuned Security Architect is measurably more accurate than a general model.

Not justified for: Design reasoning, Requirements clarification, Deployment planning — these require broad knowledge that fine-tuning narrows.

### Knowledge Injection

- **Architecture knowledge:** injected via the Level 0 architecture summary (AST-generated, never LLM-generated) at the start of every agent context.
- **Design Decision Records:** queried from semantic memory by Design and Implementation agents as part of progressive context loading.
- **Regression patterns:** queried from episodic memory by QA Manager at phase start.



### Guardrails (Output Validation)

All outputs pass through MASC (§E.6) before entering state. MASC is the primary guardrail layer. For external-facing outputs (PR descriptions, human-readable summaries), an additional sanitization pass removes credential-shaped strings and instructional content.

## E.4 Dynamic Requirements Questioning Engine

The requirements phase is the platform's most important phase and historically its most under-specified component.

### Question Bank Structure

Organized by category: business objective, functional requirements, non-functional requirements, security/compliance, performance, scalability, reliability, data integrity, API contracts, deployment constraints. Each question tagged with:

```python
@dataclass
class Question:
    id: str
    text: str
    category: str
    applies_if: Callable[[WorkflowContext], bool]
    auto_answerable_from: str | None  # "repo_intelligence" | None
    depends_on: list[str]             # Question IDs that must be answered first
```



### Auto-Answer Before Asking

Before any question reaches a human, the engine checks whether Repository Intelligence can answer it with high confidence:

- Tech stack, existing API contracts, current test coverage, existing patterns — directly retrievable from semantic memory.
- Questions the repo can answer are skipped (not "hidden" — the UI shows them as "auto-answered from repo" with the retrieved answer, so the human can see the platform did real work).
- Only questions the repo cannot answer (business objectives, non-functional targets, org constraints, policy decisions) reach the human.



### Question Dependency DAG (Partial)

```
Q1: Primary objective (always)
  └─ IF touches auth/payments/PII → Qsec1: Compliance requirements
       └─ Qsec2: Data classification
            └─ Qsec3: Regulatory constraints (GDPR, PCI)

Q2: User/consumer of this change (always)

Q3: Acceptance criteria (always)
  └─ IF work_type in [feature, new_project]:
       ├─ Q4: Performance targets
       ├─ Q5: Scalability expectations
       └─ Q6: Availability requirements (SLA, RTO, RPO)
  └─ IF work_type == bug:
       ├─ Q4b: Reproduction steps
       ├─ Q5b: Expected vs. actual behavior
       └─ Q6b: When did it start?
  └─ IF work_type == hotfix:
       ├─ Q7h: Blast radius
       └─ Q8h: Temporary workaround available?

IF repo_architecture == microservices AND affected_modules > 1:
  ├─ Qint1: Services requiring atomic update
  ├─ Qint2: API versioning requirements
  └─ Qint3: External consumers?

IF has_database_changes:
  ├─ Qdb1: Additive or modify/drop migration?
  ├─ Qdb2: Data volume affected?
  └─ Qdb3: Zero-downtime required?
```



### Exit Conditions (3-way, from original spec)

Stop when **any one** is satisfied:

1. `confidence_score ≥ floor[requirements] = 0.80` AND all mandatory questions for this work type are answered.
2. Human explicitly accepts remaining open assumptions (logged in Phase Handoff Packet).
3. Confidence cannot be raised further → `interrupt()` for HITL review.

**Fail-Closed on the exit evaluator:** if the confidence scorer fails, condition (1) cannot be satisfied → always exits via condition (3) (HITL).

## E.5 Feedback Agent

The named agent that handles repeated failure on the same module — explicitly specified here because neither prior document did so.

- **Trigger:** N consecutive failures on the same module (N = `Task.budget.max_retries_per_node`).
- **Input:** A `ReplanContext` (§B.2) — full failure history for this task and module, prior `WorkerCoordinationPacket`s, any unresolved `ClarificationEscalation`s, and episodic memory of similar past failures and how they were resolved. This is what makes each attempt strictly more informed than the last (§D.5), not a re-read of the same failure in isolation.
- **Reasoning:** "What is the root pattern across these failures, and what fundamentally different approach should the CodeGen sub-agent try?"
- **Output:** Revised `TaskDecomposition` entry with a different approach, additional context pointers, and explicit constraints.
- **If Feedback Agent's output also fails:** escalate to human (Fail-Closed). Never loop indefinitely.
- **Model tier:** High-capability (GLM-4.7) — root-cause reasoning across a failure history requires broad reasoning.



## E.6 MASC: Metacognitive Self-Correction Engine

Runs as post-node middleware in LangGraph — not as a separate agent. Validates outputs before they enter `SDLCState`. Three checks, cheapest first.

```python
class MASCEngine:
    """Post-node output validator. Cheapest-first to minimize token cost."""
    
    CONFIDENCE_THRESHOLDS = {
        "requirements": 0.80, "design": 0.85,
        "implementation": 0.75, "qa": 0.90, "deployment": 0.95,
    }
    HIGH_STAKES_PHASES = {"design", "implementation_plan", "deployment"}
    
    def validate(self, output: dict, agent_id: str, phase: str,
                 state: SDLCState) -> tuple[bool, ValidationFlag | None]:
        
        # Check 1: Schema validation — zero tokens
        if not self._validate_schema(output, agent_id):
            return False, ValidationFlag(
                source="masc", flag_type="schema_violation", severity="error", ...)
        
        # Check 2: Confidence gating — zero tokens
        if output.get("confidence", 1.0) < self.CONFIDENCE_THRESHOLDS.get(phase, 0.80):
            return False, ValidationFlag(
                source="masc", flag_type="confidence_below_threshold", severity="warning", ...)
        
        # Check 3: Semantic drift — fast model only (~200 tokens), high-stakes phases only
        if phase in self.HIGH_STAKES_PHASES:
            if self._check_semantic_drift(output, state["requirements"], state["intent_version"]):
                return False, ValidationFlag(
                    source="masc", flag_type="semantic_drift", severity="error", ...)
        
        return True, None
    
    # Fail-Closed: if MASC itself errors → treat as severity="error", route to human
```



## E.7 Intent Tracker

Maintains requirements as an evolving belief state. Prevents intent drift from corrupting ongoing implementation.

```python
class IntentTracker:
    """Runs on every new user message, including HITL responses."""
    
    def classify(self, new_message: str, current_spec: RequirementsSpec) -> IntentDiff:
        # Structured extraction: classify each claim as:
        # ADDITIVE | MODIFICATION | CONTRADICTION | IRRELEVANT
        # MODIFICATION/CONTRADICTION: require explicit human confirmation before applying
        # Increments intent_version on any spec mutation
        ...
    
    def flag_drift_mid_implementation(self, diff: IntentDiff, state: SDLCState) -> ValidationFlag | None:
        # If CONTRADICTION detected during implementation → ValidationFlag(flag_type="semantic_drift")
        # Triggers FL-11: rollback to requirements phase with HITL
        ...
```



## E.8 Full Agent Roster by Phase

*Every* `ApprovalGate` *and* `Validator` *entry is a template instance, not a separately implemented class.*

### Phase: Intake & Planning


| Agent                     | Responsibility                                      | Input → Output                                                 | Model Tier      | Tools                                        | Exit / Failure                                                                         |
| ------------------------- | --------------------------------------------------- | -------------------------------------------------------------- | --------------- | -------------------------------------------- | -------------------------------------------------------------------------------------- |
| **Planning Manager**      | Coordinates intake through requirements-ready state | Raw request → classified Task                                  | Fast            | Task classifier, Risk model, Episodic memory | Exit: Task classified. Failure: unresolvable → HITL (Fail-Closed)                      |
| **Requirements Analyst**  | Runs Dynamic Questioning Engine (§E.4)              | Raw request + repo context → RequirementsSpec + Handoff Packet | High-capability | Repo Intelligence, Questioning Engine        | Exit: 3-way condition met. Failure: user unresponsive → held open; never auto-proceeds |
| **Intent Tracker**        | Detects mutations in user intent across turns       | New message + current spec → IntentDiff                        | Fast            | None (reads state only)                      | Exit: classified and stored. Failure: ambiguous → MODIFICATION, requires HITL          |
| **Confidence Scorer**     | Computes composite confidence score (§B.4)          | Spec + retrieval coverage + precedent → confidence_score       | Fast            | Retrieval metrics, episodic lookup           | Exit: score computed. Failure (Fail-Closed): treated as below floor                    |
| `Validator`(requirements) | Independent consistency check                       | RequirementsSpec → pass/fail + gaps                            | Fast            | Consistency checker                          | Failure: FeedbackReport to Requirements Analyst                                        |
| `ApprovalGate`(scope)     | Sign-off on scope before design spend               | Requirements + assumption log                                  | —               | Interrupt/resume (§D.7)                      | When: risk ≥ Medium. Failure: reject → Requirements Analyst                            |




### Phase: Architecture & Design


| Agent                         | Responsibility                                                                          | Input → Output                                                | Model Tier      | Tools                                                               | Exit / Failure                                                                  |
| ----------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------- | --------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| **Design Manager**            | Coordinates design; allocates heavy reasoning budget                                    | Approved requirements → design package                        | High-capability | —                                                                   | Exit: design package complete. Failure: repeated rejection → HITL               |
| **Repo Architecture Analyst** | Grounds design in actual codebase structure                                             | Requirements + repo graph → architecture-fit analysis         | Fast            | Repo Intelligence (structural queries, 2-hop from affected modules) | Exit: analysis attached. Failure: low-confidence retrieval → flagged            |
| **Security Architect**        | Threat modeling; security design addendum; compliance check                             | ArchitectureDoc + security classification → security addendum | High-capability | Semgrep (existing patterns); STRIDE model                           | When: `security_classification ≠ low` OR `touches_shared_infra`. Skip otherwise |
| `Validator`(design)           | Checks design against system-design checklist (boundaries, contracts, failure handling) | Design package → pass/fail + gaps                             | High-capability | Checklist evaluator                                                 | Failure: FeedbackReport to Design Manager; 5× max before HITL                   |
| `ApprovalGate`(design)        | Architecture sign-off                                                                   | Design package + findings                                     | —               | Interrupt/resume                                                    | When: risk ≥ Medium                                                             |




### Phase: Implementation


| Agent                       | Responsibility                                                          | Input → Output                                                | Model Tier                                         | Tools                                                                                   | Exit / Failure                                                                                           |
| --------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------- | -------------------------------------------------- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| **Implementation Manager**  | Decomposes design into tasks; dependency-aware execution ordering; pre-dispatch overlap check (§D.4.2) before `Send` | Approved design → TaskDecomposition                           | High-capability                                    | `get_dependencies`, `get_dependents`                                                    | Exit: no circular deps; all components covered; no obvious file overlap in same parallel group. Failure: overlapping ownership → resolve before dispatch |
| **CodeGen Sub-agent (×N)**  | Implements one module/scope per instance (parallel via Send API); emits `WorkerCoordinationPacket` on exit (§D.9.2), or `ClarificationEscalation` + stops (§D.9.3) if blocked | Module spec + progressive context → diff + WCP                | Fast (simple) / High-capability (complex refactor) | `get_symbol_signature`, `get_symbol_body`, `get_callers`, `get_file_structure`, sandbox | Exit: diff + WCP produced; self-check clean. Failure 3×: Feedback Agent. Never contacts another CodeGen instance directly (§D.9.1) |
| **Fan-in Coordinator**      | Deterministic (not an agent, not an LLM call) — overlap + WCP semantic-conflict detection, merge/serialize decision, replan trigger (§D.4.1) | All branch diffs + WCPs → merge-eligible set or serialize/replan instruction | — (no model call) | File-set/diff analysis, `WorkerCoordinationPacket` fields | Exit: clean merge or all conflicts serialized/replanned. Never silently auto-merges |
| `Validator`(implementation) | Static validation: lint/type/security (independent of CodeGen); **runs per branch before Fan-in** (§D.4.0) | Branch diff → pass/fail + findings                                   | None (tools only)                                  | ruff, mypy, Semgrep                                                                     | Failure: FeedbackReport to CodeGen sub-agent (FL-04); 3× max                                                     |
| **Feedback Agent**          | Synthesizes root cause of repeated failure; proposes different approach | `ReplanContext` (failure history, WCPs, episodic memory) → revised task instructions | High-capability                                    | Episodic memory                                                                         | Trigger: N consecutive failures on same module. Failure: HITL escalation                                 |
| **Integration Validator**   | Verifies new code integrates correctly; catches interface mismatches    | All merged diffs + interface contracts → pass/fail            | High-capability                                    | `get_callers`, `get_callees`, sandbox integration tests                                 | Failure: FeedbackReport to Implementation Manager                                                        |

**Note:** `Integration Validator` is a `BaseAgent` with tool calls (RI + sandbox tests), **not** a `Validator` template instance. It runs on the **merged** diff set after Fan-in. `Validator(implementation)` is a `Validator` template instance that runs **per branch before Fan-in** (§D.4.0).




### Phase: QA & Testing


| Agent                                  | Responsibility                                                      | Input → Output                              | Model Tier                                       | Tools                               | Exit / Failure                                                                              |
| -------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------ | ----------------------------------- | ------------------------------------------------------------------------------------------- |
| **QA Manager**                         | Computes QA depth from risk tier; dispatches sub-agents             | Task + risk tier → QA plan                  | Fast                                             | Workflow Policy Engine              | Exit: QA plan executed. Any sub-agent critical-fail → routes to implementation              |
| **Bug Validation Agent**               | Reproduces reported bug *before* any fix                            | Bug report + repo → reproduction result     | High-capability                                  | Sandbox execution                   | When: work_type = bug/hotfix. Not-reproduced → return task to requirements                  |
| **Dependency Impact Agent**            | BFS traversal; expands test scope to affected downstream components | Diff + dependency graph → expanded scope    | None (graph traversal)                           | `get_impact_set`, Repo Intelligence | Exit: expanded scope defined                                                                |
| **Unit/Integration Test Agent**        | Runs and extends test coverage, test-impact-analysis scoped         | Diff + test suite → results                 | Fast                                             | pytest, test-impact-analysis        | Exit: green. Failure: FeedbackReport to implementation                                      |
| **Security/Performance QA sub-agents** | Risk-gated deep checks                                              | Diff + risk tier → findings                 | Fast (Semgrep inline) / None (CodeQL runs async) | Semgrep, CodeQL, k6/Locust          | When: risk ≥ Medium (Security); risk ≥ High (Performance)                                   |
| **Spec QA Agent**                      | Verifies implementation matches requirements; detects scope creep   | Diff + RequirementsSpec → compliance report | High-capability                                  | Structured comparison               | Always runs. Failure → FeedbackReport to implementation; 3× → Design phase if design defect |
| `Validator`(qa)                        | Confirms QA plan matches risk tier requirements                     | QA plan + results → plan-compliance check   | Fast                                             | Policy checker                      | Failure: QA Manager re-runs missing checks                                                  |
| `ApprovalGate`(release)                | Gate before Review phase                                            | Full QA evidence bundle                     | —                                                | Interrupt/resume                    | When: risk ≥ Medium                                                                         |




### Phase: Review, Release & Monitoring


| Agent                       | Responsibility                                                                   | Input → Output                                         | Model Tier      | Tools                                      | Exit / Failure                                                              |
| --------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------ | --------------- | ------------------------------------------ | --------------------------------------------------------------------------- |
| **Review Manager**          | Coordinates diff review against design + standards                               | Diff + design + QA evidence → review outcome           | High-capability | Repo Intelligence, style/standards checker | Exit: approved for release. Failure: changes-requested → implementation     |
| `ApprovalGate`(pr)          | Standard PR review; mandatory for Medium+ risk                                   | PR + evidence bundle                                   | —               | Git provider MCP                           | Failure: changes-requested → implementation                                 |
| **Release Manager**         | Coordinates deployment via existing CI/CD                                        | Merged PR → deployment plan + strategy selection       | High-capability | CI/CD adapter (never direct cloud API)     | Exit: deployed. Failure: automated rollback trigger                         |
| **Rollback Sub-agent**      | Executes rollback plan on deployment failure or incident                         | Deployment + rollback plan → reverted state            | Fast            | CI/CD adapter                              | Failure: IMMEDIATE human escalation                                         |
| `ApprovalGate`(deployment)  | **Mandatory for every production deploy regardless of confidence (Principle 4)** | Deployment plan + evidence                             | —               | Interrupt/resume                           | Always fires for production. Timeout → hold, never auto-approve             |
| **Monitoring Manager**      | Watches deployed change for bake-in period; canary analysis                      | Deployment + telemetry → incident/no-incident          | Fast            | OTel pipeline                              | Exit: bake-in clean. Incident → **new Task** via lineage (never loops back) |


---



# Part F — Dynamic Workflow Engine



## F.1 WorkflowProfile

Computed once at intake, attached to Task, consumed by every downstream node.

```python
from pydantic import BaseModel
from typing import Literal

Checkpoint = Literal["scope", "design", "security", "release", "pr", "deployment"]

class WorkflowProfile(BaseModel):
    agent_set: list[str]              # which specialist/validator agents are active
    execution_order: Literal["sequential", "parallel_where_independent"]
    qa_depth: Literal["minimal", "standard", "deep", "exhaustive"]
    model_tier: Literal["fast_cheap", "balanced", "frontier"]
    approval_requirements: list[Checkpoint]
    max_parallelism: int              # capped by repo_scale (§F.2)
    cost_budget_usd: float            # derived from risk tier and work type

    @classmethod
    def most_conservative(cls) -> "WorkflowProfile":
        """Fail-Closed default (Principle 8). Used by Phases 05–09 until Phase 10
        replaces hardcoded call sites with resolve_workflow_profile()."""
        return cls(
            agent_set=["all"],        # every agent active — no shortcuts
            execution_order="parallel_where_independent",
            qa_depth="standard",
            model_tier="balanced",
            approval_requirements=["scope", "design", "release", "pr", "deployment"],
            max_parallelism=2,
            cost_budget_usd=20.0,
        )
```

**Phases 05–09 binding rule:** every `ApprovalGate.applies_when`, QA depth setting, and model tier assignment MUST behave as if `WorkflowProfile.most_conservative()` were resolved — do not hand-code shortcut paths in individual agents. Phase 10 replaces these hardcoded defaults with `resolve_workflow_profile()` call sites.



## F.2 WorkflowContext Schema

```python
from pydantic import BaseModel, computed_field

class WorkflowContext(BaseModel):
    # Task properties
    work_type: WorkType
    methodology: Methodology
    risk_tier: RiskTier
    confidence_score: float = 0.0
    
    # Repository properties
    repo_architecture: str         # monolith | modular_monolith | microservices
    repo_scale: str                # small(<1k) | medium(<10k) | large(<100k) | enterprise(100k+)
    affected_module_count: int = 0
    dependency_fan_out: int = 0
    touches_shared_infra: bool = False
    has_database_changes: bool = False
    has_api_contract_changes: bool = False
    has_ui_changes: bool = False
    is_greenfield: bool = False
    
    # Engineering constraints
    production_criticality: str    # low | medium | high | critical
    requires_backward_compat: bool = False
    has_external_consumers: bool = False
    
    # Derived properties
    @computed_field
    def requires_full_design_phase(self) -> bool:
        return (self.is_greenfield
                or self.work_type in [WorkType.MIGRATION, WorkType.NEW_PROJECT]
                or (self.risk_tier in [RiskTier.HIGH, RiskTier.CRITICAL]
                    and self.touches_shared_infra))
    
    @computed_field
    def max_parallel_impl_agents(self) -> int:
        scale_caps = {"enterprise": 8, "large": 5, "medium": 3, "small": 2}
        return scale_caps.get(self.repo_scale, 3)
```



## F.3 Decision Rules (Ordered, First-Match-Wins)

Implementable directly as code. Every pair of rules is unit-tested for non-overlap.

```python
def resolve_workflow_profile(task: Task, ctx: WorkflowContext) -> WorkflowProfile:
    profile = WorkflowProfile.most_conservative()  # Fail-Closed default (Principle 8)
    
    # Rule 1 — Critical risk: maximum caution, regardless of confidence
    if task.risk_tier == RiskTier.CRITICAL:
        profile.approval_requirements = [SCOPE, DESIGN, SECURITY, RELEASE, DEPLOYMENT]
        profile.qa_depth = EXHAUSTIVE
        profile.model_tier = FRONTIER
        return profile
    
    # Rule 2 — Production hotfixes: never auto-merge, fast path, Bug Validation always runs
    if task.type == WorkType.HOTFIX and is_production(task.repo_refs):
        profile.approval_requirements += [DEPLOYMENT]
        profile.execution_order = SEQUENTIAL_FAST_PATH
        profile.qa_depth = STANDARD_PLUS_BUG_VALIDATION
        return profile
    
    # Rule 3 — Low confidence (or scorer failed): escalate regardless of risk tier
    if ctx.confidence_score < CONFIDENCE_FLOOR or ctx.confidence_score is None:
        profile.approval_requirements += [SCOPE, DESIGN]
        return profile
    
    # Rule 4 — Low risk + high confidence: auto-merge eligible (still logged/revertible)
    if task.risk_tier == RiskTier.LOW and ctx.confidence_score > AUTO_MERGE_CEILING:
        profile.approval_requirements = []
        profile.model_tier = FAST_CHEAP
        return profile
    
    # Rule 5 — Default: standard Medium-risk path
    profile.approval_requirements += [RELEASE, PR]
    profile.qa_depth = STANDARD
    profile.model_tier = BALANCED
    return profile

def escalate_model_tier(node_state: NodeExecutionState) -> ModelTier:
    """Escalation-on-Repeated-Rejection: escalates when validators repeatedly reject."""
    if node_state.validator_rejections >= 2 and node_state.model_tier == FAST_CHEAP:
        return BALANCED
    if node_state.validator_rejections >= 2 and node_state.model_tier == BALANCED:
        return FRONTIER
    if node_state.validator_rejections >= node_state.task.budget.max_retries_per_node:
        route_to(FEEDBACK_AGENT)  # then HITL if still failing — Fail-Closed
    return node_state.model_tier
```



## F.4 Agent Selection Rules


| Condition                  | Add Agent                                                    | Skip Agent                                            |
| -------------------------- | ------------------------------------------------------------ | ----------------------------------------------------- |
| `work_type == hotfix`      | Bug Validation Agent, Rollback Sub-agent                     | Full Design phase, Security Architect                 |
| `risk_tier >= HIGH`        | Security QA, Performance QA, Exploratory Testing             | —                                                     |
| `risk_tier == LOW`         | —                                                            | Mutation Testing, Exploratory Testing, Performance QA |
| `has_database_changes`     | DB Migration Validator                                       | —                                                     |
| `has_api_contract_changes` | API Contract Validator (schemathesis), Consumer Notification | —                                                     |
| `has_ui_changes`           | UI QA (Playwright), Accessibility QA (axe-core)              | —                                                     |
| `repo_scale == enterprise` | Shard Coordinator (§G.4)                                     | —                                                     |
| `is_greenfield`            | Architecture Decision Agent                                  | Regression Analyst                                    |
| `methodology == waterfall` | Stage Gate Enforcer                                          | —                                                     |
| `touches_shared_infra`     | Security Architect (forced active)                           | —                                                     |




## F.5 Feedback Loop Registry

Every loop is named, parametrized, and registered. Not scattered through agent code.


| Loop ID | Trigger                        | Source Agent                | Target Agent           | Max Iterations | Rollback Depth  | HITL? |
| ------- | ------------------------------ | --------------------------- | ---------------------- | -------------- | --------------- | ----- |
| FL-01   | Requirements spec gaps         | `Validator`(requirements)   | Requirements Analyst   | Unlimited      | Same phase      | No    |
| FL-02   | Design checklist fail          | `Validator`(design)         | Design Manager         | 5              | Same phase      | No    |
| FL-03   | Design reveals requirement gap | `Validator`(design)         | Requirements phase     | 1              | Full phase      | Yes   |
| FL-04   | Static analysis fail           | `Validator`(implementation) | CodeGen Sub-agent      | 3              | Same task       | No    |
| FL-05   | Integration fail               | Integration Validator       | Implementation Manager | 2              | Re-assign tasks | No    |
| FL-06   | Spec compliance fail           | Spec QA Agent               | Implementation phase   | 3              | Full phase      | No    |
| FL-07   | QA reveals design defect       | Spec QA Agent               | Design phase           | 1              | Full phase      | Yes   |
| FL-08   | Critical security finding      | Security QA                 | Design phase           | 1              | Full phase      | Yes   |
| FL-09   | Deployment health degraded     | Health Monitor              | CI/CD rollback         | Auto           | Automated       | No    |
| FL-10   | MASC critical anomaly          | MASC Engine                 | Previous checkpoint    | 1              | Phase entry     | Yes   |
| FL-11   | Intent contradiction detected  | Intent Tracker              | Requirements phase     | 1              | Phase entry     | Yes   |


**Global guard:** `task.rollback_count ≥ (max_retries_per_node × active_phases)` → suspend task, preserve full state, notify human, block further autonomous execution.

---



# Part G — Repository Intelligence



## G.1 Design Decision: Long-Lived Shared Service

Repository Intelligence is **not** a per-task LangGraph subgraph. Its lifecycle (continuously updated, cross-task, federated across shards) doesn't fit task-scoped graph state. It is a long-lived service invoked via tool calls from any subgraph.

## G.2 Layered Index Architecture


| Layer  | Contents                                        | Update Pattern                                                     |
| ------ | ----------------------------------------------- | ------------------------------------------------------------------ |
| **L0** | Raw files + git metadata                        | Real-time via git hooks                                            |
| **L1** | AST/symbol index (Tree-sitter)                  | Incremental, per changed file                                      |
| **L2** | Dependency/call graph (NetworkX→Neo4j)          | Incremental, changed file + 1–2 hop dependents                     |
| **L3** | Semantic embeddings (pgvector→Qdrant)           | Incremental, same trigger as L1/L2                                 |
| **L4** | Architecture/knowledge graph + cached summaries | Invalidated by content-hash + dependency-hash; refreshed on demand |




## G.3 Tool Stack & Rationale


| Purpose                             | Recommended                                                              | Alternative                 | Why Chosen                                                                                                                                           |
| ----------------------------------- | ------------------------------------------------------------------------ | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Symbol parsing / AST**            | **Tree-sitter**                                                          | Per-language LSP servers    | Multi-language; fast incremental parsing; embeddable; kept as L1 foundation                                                                          |
| **Code search / lexical index**     | **Zoekt** (trigram-based)                                                | ripgrep over files          | Proven at Sourcegraph scale; O(1) query with pre-built index; not O(n) file scanning                                                                 |
| **Dependency/call graph**           | **NetworkX** (MVP) → **Neo4j** (at scale)                                | KuzuDB                      | NetworkX: zero infra for MVP; Neo4j: multi-hop Cypher queries at scale. KuzuDB is embedded-only — wrong for a shared service with concurrent readers |
| **Vector search**                   | **pgvector** (MVP) → **Qdrant** (at scale)                               | Pinecone                    | pgvector reuses Postgres infra at MVP; Qdrant is purpose-built ANN with horizontal scaling                                                           |
| **Deep security semantic**          | **CodeQL** (periodic deep)                                               | Semgrep alone               | CodeQL's dataflow analysis catches classes of issues pattern-matching cannot. Use both at different tiers                                            |
| **Repo context / token efficiency** | **Aider-style PageRank repo map**                                        | Full-repo LLM summarization | Proven technique: PageRank-weighted file/symbol map gives a model repo overview at ~1000 tokens vs. brute-force summarization                        |
| **Hybrid retrieval fusion**         | **Reciprocal Rank Fusion (RRF)** over Zoekt + pgvector + graph expansion | Simple score averaging      | RRF is more robust to score distribution differences across retrieval methods                                                                        |


**Note on SCIP (from V2):** SCIP is a *protocol* for writing language-server symbol data to a file — not a search engine. Tree-sitter handles parsing; Zoekt handles indexed search. SCIP-formatted exports can be used to populate the graph DB if precision demands compiler-grade resolution, but it is not a retrieval mechanism.

## G.4 Federated Repository Intelligence for 100k–1M+ Files

At 1M+ files, a single flat index makes query cost proportional to total repo size, not task relevance. One hot service's churn slows retrieval for every other team.

**Design:** Partition L1–L4 into **domain shards** aligned to existing service or team-ownership boundaries (validated against the L2 dependency graph, not inferred from directory structure alone). Each shard: own AST index, vector sub-index, local dependency graph. A **global index-of-indices** stores only: shard boundaries, cross-shard dependency edges (API contracts, shared libraries), shard-level L4 summaries.

**Query flow:**

1. Request hits global index-of-indices → determines relevant shard(s).
2. Drills into only those shards' full indices.
3. Cross-shard queries ("what calls this API org-wide") route through the cross-shard edge index specifically.

**Shard boundary validation:** boundaries are drawn from the L2 dependency graph, not from directory structure alone. A boundary is valid if the cross-boundary edge count is low relative to within-shard edge count. This prevents splitting a tightly-coupled component across shards.

## G.5 Incremental Indexing & Freshness

- Git-diff-triggered re-indexing scoped to changed files + 1–2 hop dependents.
- **Nightly full re-index** as drift-safety net.
- L4 summaries invalidated via content-hash + dependency-hash keys (staleness is detectable, not silent).
- Target incremental update latency: < 10s for a typical commit (1–20 files).



## G.6 RepositoryIntelligence API

Single interface. Agents never query the graph DB or vector store directly.

```python
class RepositoryIntelligence:
    # ── Structural (zero LLM cost) ──────────────────────────────────────
    async def get_callers(self, symbol_id: str, depth: int = 1) -> list[Symbol]: ...
    async def get_callees(self, symbol_id: str, depth: int = 1) -> list[Symbol]: ...
    async def get_dependencies(self, file_path: str) -> list[str]: ...
    async def get_dependents(self, file_path: str) -> list[str]: ...
    async def get_impact_set(self, changed_files: list[str]) -> ImpactSet: ...
    async def get_symbol_signature(self, symbol_id: str) -> str: ...
    async def get_symbol_body(self, symbol_id: str) -> str: ...
    async def get_file_structure(self, file_path: str) -> list[Symbol]: ...
    
    # ── Architecture (AST-generated, cached) ───────────────────────────
    async def get_architecture_summary(self) -> str: ...     # ~1000–2000 tokens
    async def get_aider_repo_map(self, scope: list[str]) -> str: ...  # PageRank-weighted
    
    # ── Semantic (vector search) ────────────────────────────────────────
    async def search_concepts(self, query: str, top_k: int = 5) -> list[CodeChunk]: ...
    async def find_similar_implementations(self, code: str, top_k: int = 3) -> list[CodeChunk]: ...
    
    # ── Hybrid (structural + semantic, fused via RRF) ───────────────────
    async def find_relevant_context(self, task: str, scope: list[str],
                                    max_tokens: int) -> ContextBundle: ...
    
    # ── Historical ─────────────────────────────────────────────────────
    async def get_regression_history(self, modules: list[str]) -> list[RegressionRecord]: ...
    async def get_design_decisions(self, modules: list[str]) -> list[ADR]: ...
    async def get_change_frequency(self, file_path: str, days: int = 90) -> float: ...
```

### G.6.1 Supporting Types (Canonical Minimal Models)

```python
from pydantic import BaseModel

class Symbol(BaseModel):
    id: str              # symbol_id: "{file_path}::{qualified_name}"
    kind: str            # function | class | method | module | ...
    name: str
    file_path: str
    start_line: int
    end_line: int
    signature: str | None = None
    docstring: str | None = None

class CodeChunk(BaseModel):
    symbol_id: str | None
    file_path: str
    chunk_text: str
    content_hash: str
    start_line: int
    end_line: int

class ImpactSet(BaseModel):
    changed_files: list[str]
    affected_files: list[str]       # dependents within configured BFS depth
    affected_symbols: list[str]     # symbol_ids
    depth: int

class ContextBundle(BaseModel):
    chunks: list[CodeChunk]
    total_tokens: int
    truncated: bool                 # True if max_tokens forced early stop
```

### G.6.2 Repository Intelligence Failure Contracts (Fail-Closed)

| Failure | Caller context | Behavior |
|---|---|---|
| RI timeout / unavailable | Worker mid-task | `ClarificationEscalation(ri_consulted=true)` with empty evidence; worker stops (`blocked=true`) |
| RI timeout / unavailable | Fan-in semantic cross-check (§D.4.1.1 step 4) | Treat as conflict → serialize-and-rerun or Manager replan |
| RI timeout / unavailable | Confidence Scorer / MASC | Treat confidence as below floor → block / escalate (§B.4) |
| RI returns empty for required query | Worker | Escalate via ClarificationEscalation — never guess |
| Malformed RI response | Any | Fail-Closed → escalate; log `ValidationFlag(source="tool_error")` |

Agents never query the graph DB or vector store directly — all failures surface through the `RepositoryIntelligence` interface above.



## G.7 Architecture Summary (AST-Generated, Never LLM-Generated)

```json
{
  "services": ["auth", "payments", "notifications"],
  "service_map": {
    "auth": {
      "entry_points": ["POST /login", "POST /refresh"],
      "key_symbols": ["UserService", "TokenManager"],
      "dependencies": ["db.users", "cache.sessions"],
      "tech_stack": ["FastAPI", "PostgreSQL", "Redis"]
    }
  },
  "shared_modules": ["utils.logging", "utils.validation"],
  "database_entities": ["User", "Session", "AuditLog"],
  "api_boundaries": ["REST /api/v1", "gRPC auth.proto"],
  "cross_shard_deps": [{"from": "payments", "to": "auth", "via": "auth.TokenManager"}]
}
```

Generated by Tree-sitter AST walker. Update trigger: structural graph change in incremental index. This is the Level 0 context always injected into every agent.

---



# Part H — Context Engineering



## H.1 Context Budget (Derived from Model Window)

```python
class ContextBudget:
    MODEL_MAX = 128_000      # GLM-4.7 (update when provider changes)
    THRESHOLD  = 0.80        # Never fill more than 80%
    USABLE     = 102_400

    # Non-negotiable reservations
    SYSTEM_PROMPT     = 2_000
    OUTPUT_RESERVE    = 4_000
    CONVERSATION_HOT  = 8_000
    ARCH_SUMMARY      = 2_000    # L0 context, always present

    AVAILABLE = USABLE - SYSTEM_PROMPT - OUTPUT_RESERVE - CONVERSATION_HOT - ARCH_SUMMARY
    # = 86,400 tokens for retrieved context

    PHASE_BUDGETS = {
        "requirements":    {"task_context": 4000, "precedents": 2000, "history": 1000},
        "design":          {"repo_map": 5000, "structural_graph": 12000, "adrs": 3000, "patterns": 3000},
        "implementation":  {"task_spec": 3000, "symbols": 8000, "interfaces": 2000},
        "qa":              {"diff": 10000, "impact_set": 5000, "regression_history": 2000},
        "deployment":      {"config": 3000, "deploy_history": 1000},
    }
```



## H.2 Aider-Style PageRank Repo Map

The Aider codebase established a highly effective technique: build a map of the repo's most important files and symbols by computing PageRank over the codebase's import/reference graph. Files referenced by many other files rank higher. This gives a model a dense, token-efficient overview of what matters most in the codebase.

```
At context assembly time:
  1. Get PageRank scores for all files in affected shard
  2. Build repo map: top-K files by PageRank, with their key symbols and signatures
  3. Inject map into design and implementation agent contexts as Level 0.5 context
     (after architecture summary, before progressive expansion)

Token cost: ~1,000–3,000 tokens
Value: model understands which files matter before retrieving any specific content
```



## H.3 Compression Pipeline (5 Steps, Cheapest First)

```
Input: Raw context candidates (potentially over budget)

Step 1 — Structural filtering (free, deterministic)
  Remove files not in dependency graph of changed modules
  Remove symbols not referenced by changed code

Step 2 — Deduplication (free)
  Hash-based dedup of repeated code blocks
  Merge overlapping code ranges

Step 3 — AST-boundary skeletal compression (free)
  Replace function bodies with signatures + docstrings (Level 1)
  Expand to full body (Level 2) only on explicit agent tool call

Step 4 — LRU eviction (free)
  Evict oldest resolved context chunks
  Preserve: active constraints, open ambiguities, recent tool results

Step 5 — LLM summarization (fast model only, ~300–500 tokens)
  Summarize cold conversation history into procedural memory block
  Only if Steps 1–4 still over budget

Fallback: If still over budget after Step 5 → split task into smaller sub-tasks
```



## H.4 Progressive Context Loading (Tool-Based)

Agents start with minimal context and expand on demand via tool calls. This improves both cost efficiency and accuracy (avoids "lost in the middle" degradation on long contexts).

```python
# Tools available to every agent for on-demand context expansion
CONTEXT_EXPANSION_TOOLS = [
    "get_symbol_signature",     # Level 1: signature + docstring
    "get_symbol_body",          # Level 2: full implementation
    "get_callers",              # Call graph expansion (depth 1 or 2)
    "get_callees",
    "get_file_structure",       # File's class/function list (no bodies)
    "search_codebase",          # Semantic search for patterns/concepts
    "get_aider_repo_map",       # PageRank-weighted overview of a scope
]
```

Agents receive only Level 0 (architecture summary) + Level 0.5 (repo map for scope) initially. All deeper context is agent-requested.

---



# Part I — Model Abstraction Layer



## I.1 Adapter Interface

```python
from langchain_core.language_models import BaseChatModel  # Primary base

class ModelAdapter(Protocol):
    """All orchestration code talks to ModelAdapter — never to a provider SDK directly."""
    def complete(self, request: ModelRequest) -> ModelResponse: ...
    def stream(self, request: ModelRequest) -> Iterator[ModelChunk]: ...
    def call_tools(self, request: ModelRequest, tools: list[ToolSpec]) -> ModelResponse: ...
    def embed(self, texts: list[str]) -> list[Vector]: ...
    @property
    def pricing(self) -> ModelPricing: ...
    @property
    def capability_score(self) -> int: ...  # 1–10, used by ModelRouter
```

**Build choice:** use `LangChain BaseChatModel` as the base (already a LangGraph dependency; structured output, tool-calling, streaming, and retry semantics come essentially for free). LiteLLM as an optional normalization layer if GLM's endpoint has compatibility issues — not the primary abstraction.

**GLM assumption to verify before implementation:** GLM Developer API is assumed OpenAI-compatible at the endpoint level. If true, the GLM adapter is a thin `ChatOpenAI`-compatible wrapper. Verify against live documentation.

## I.2 Model Routing

```python
CAPABILITY_REQUIREMENTS = {
    # (phase, operation): minimum_capability_score
    ("requirements", "ambiguity_detection"):   8,
    ("design", "architecture"):                9,
    ("design", "security_analysis"):           8,
    ("design", "self_critique"):               8,  # reflection pass
    ("implementation", "code_generation"):     6,  # most tasks → fast model
    ("implementation", "complex_refactor"):    8,
    ("implementation", "feedback_synthesis"):  9,  # Feedback Agent
    ("qa", "spec_validation"):                 7,
    ("qa", "static_analysis"):                 1,  # tool-only, no LLM
    ("any", "summarization"):                  3,
    ("any", "intent_classification"):          4,  # Intent Tracker
    ("masc", "semantic_drift"):                4,  # fast model sufficient
}
```

Runtime `ModelRouter.select(phase, operation, context)` returns cheapest model meeting capability requirement, adjusted up for high-risk tasks. `escalate_model_tier()` (§F.3) upgrades on repeated rejection.

## I.3 Circuit Breaker & Resilience

If the primary provider (GLM) is unavailable or error-rate exceeds threshold mid-task: task **pauses** (checkpointed), not fails. Can resume once provider recovers or fallback adapter is configured. Architecturally supported from day one even though only one provider is implemented initially.

## I.4 Adding a Provider (Verified Checklist)

- [ ] New class implements `ModelAdapter`
- [ ] Registered in pricing registry  
- [ ] Zero changes to any file outside `model_adapters/`
- [ ] Passes same contract test suite as GLM adapter
- [ ] Golden-dataset regression run side-by-side with existing provider(s)



## I.5 Cost & Token Tracking

`packages/model_adapters/telemetry.py` wraps every `ModelAdapter` call. It writes `cost_tracking` via `BudgetTracker` and opens an `llm_call` span on `TelemetrySink` (§B.8). Versioned pricing registry (model → $/1M tokens in/out) normalizes cost across providers. Never rely on provider-reported cost fields alone — not consistently available across providers. This module must not import OpenTelemetry; the sink implementation does.

---



# Part J — MCP & External Integrations



## J.1 Integration Recommendations

*MCP server availability moves fast — re-verify maturity before committing implementation time.*


| Service                               | Recommendation                                                                                            |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **GitHub**                            | Official MCP server — use directly                                                                        |
| **GitLab**                            | Evaluate community server maturity; fall back to adapter pattern if insufficient                          |
| **Jira / Confluence**                 | Atlassian official remote MCP server — use directly                                                       |
| **Slack**                             | Use directly — primary channel for HITL notifications                                                     |
| **Linear**                            | MCP support available — use directly                                                                      |
| **Azure DevOps**                      | Less mature — build thin custom adapter following MCP conventions                                         |
| **CI/CD** (GitHub Actions, GitLab CI) | Via git provider MCP or direct webhook; fine here                                                         |
| **Cloud providers**                   | Treat as **read-only observability only**; provisioning always behind human-approved IaC pipelines (§B.6) |
| **Databases**                         | Read-only, task-scoped credentials only                                                                   |




## J.2 Adapter Pattern for Missing MCP Servers

Any external service without a mature MCP server gets a thin internal MCP-server wrapper around its REST API. This makes every external tool present the same interface shape to the orchestrator, regardless of underlying maturity.

## J.3 Idempotency

All MCP tool calls carry an idempotency key (stored in PostgreSQL). Duplicate triggers (from retries or resumed checkpoints) produce the same result, not duplicate side effects.

---



# Part K — Advanced Quality Assurance



## K.1 QA Activation Matrix


| QA Check                                          | Trigger Condition                           | Tool                                 | LLM Required?  |
| ------------------------------------------------- | ------------------------------------------- | ------------------------------------ | -------------- |
| Static Analysis (lint/type)                       | Always                                      | ruff, mypy                           | No             |
| Secrets Scanning                                  | Always                                      | detect-secrets                       | No             |
| Dependency Vulnerability                          | Always                                      | pip-audit / OSV-Scanner              | No             |
| Unit + Integration Tests (impact-analysis scoped) | Always                                      | pytest + test-impact-analysis        | No             |
| Spec QA (requirement coverage)                    | Always                                      | Structured comparison                | Yes (semantic) |
| Security SAST (inline)                            | risk ≥ Medium                               | Semgrep                              | No             |
| Security Deep (dataflow)                          | risk ≥ High, periodic                       | CodeQL                               | No             |
| License / Supply-chain                            | risk ≥ Medium                               | OSV-Scanner / Trivy                  | No             |
| API Contract Fuzzing                              | `has_api_contract_changes`                  | schemathesis                         | No             |
| Mutation Testing                                  | risk ≥ High, **critical-path modules only** | mutmut (Python) / Stryker (JS)       | No             |
| Property-Based Testing                            | risk ≥ Medium, pure functions               | Hypothesis / fast-check              | No             |
| Exploratory Testing                               | risk ≥ High, UI changes                     | LLM-generated scenarios + Playwright | Yes            |
| Performance QA                                    | risk ≥ High, perf-sensitive path            | k6 / Locust                          | No             |
| Accessibility QA                                  | `has_ui_changes`                            | axe-core                             | No             |
| DAST                                              | `production_criticality == critical`        | OWASP ZAP                            | No             |


**Cost observation:** 13 of 15 QA checks use deterministic tools with zero LLM cost. LLM is required only for Spec QA and Exploratory Testing.

## K.2 Test-Impact Analysis

Default scope for every task: run only tests touching changed code + their downstream dependents (derived from L2 dependency graph). Full test suite only for Critical risk tier or explicitly triggered. Prevents the full-suite bottleneck at scale.

## K.3 Bug Validation Protocol

For work_type `bug` or `hotfix`:

1. Bug Validation Agent reproduces the reported bug **before any fix agent runs**.
2. If reproduction fails → task returned to requirements phase for re-scoping ("bug not reproducible as reported").
3. Fix agent's output validated against: does it resolve the reproduction case?
4. Regression test generated from reproduction steps, committed alongside fix.



## K.4 Regression Test Generation

After every passing QA:

1. QA evidence bundle → fast model generates regression test cases targeting: each bug found, each edge case from exploratory testing.
2. Tests formatted as pytest fixtures, committed to test suite alongside implementation PR.
3. Test metadata stored: `{test_id, covers_requirement_id, covers_module, generated_by_task_id}`.
4. Failure pattern stored in episodic memory: `{module, failure_type, fix_pattern}`.



## K.5 Evidence Bundle Standard

Every task completion produces a structured evidence bundle attached to the PR and stored in the blackboard:

- Coverage delta (before/after)
- Static analysis results (severity counts)
- Security findings (severity breakdown)
- Mutation score (if run)
- Test results (pass/fail/skip)
- Spec compliance report
- Bug reproduction result (for bug/hotfix)
- Risk score at QA entry

---



# Part L — Evaluation Framework



## L.1 Automated Scoring Pipeline

Every task completion triggers evaluation automatically.

```
Task completes
  → EvaluationPipeline.score(task_id) [runs async, within 60s]
  → Parallel:
      ├── fix_rate = correct_files / required_files
      ├── token_efficiency = fix_rate / (total_tokens / 1000)
      ├── cost_usd = Σ(input_tokens × price_in + output_tokens × price_out)
      ├── hitl_count = len(hitl_history)
      ├── rollback_count from SDLCState
      ├── cycle_time = completed_at - created_at
      └── attribution_accuracy (maps failures to root-cause agent)
  → KPIStore.record(task_id, scores)
  → Dashboard.update()
```



## L.2 KPI Reference



### Task-Level


| KPI                  | Formula                                           | Target                |
| -------------------- | ------------------------------------------------- | --------------------- |
| **Fix Rate**         | `correct_files / required_files` (partial credit) | > 0.85 for routine    |
| **Token Efficiency** | `fix_rate / (total_tokens / 1000)`                | Improving trend       |
| **Cost per Task**    | `Σ(token × price)` per provider                   | < budget threshold    |
| **HITL Rate**        | `hitl_count / task_count`                         | < 2 for routine       |
| **Rollback Rate**    | `rollback_count / task_count`                     | < 10%                 |
| **Cycle Time**       | `completed_at - created_at`                       | Defined per work_type |




### Phase-Level


| Phase          | Primary KPI                         | Target                 |
| -------------- | ----------------------------------- | ---------------------- |
| Requirements   | Clarification turns before exit     | < 5 for feature        |
| Requirements   | Ambiguity rate                      | < 10% open ambiguities |
| Design         | Coverage: requirements covered      | 100%                   |
| Design         | Rework rate                         | < 20%                  |
| Implementation | First-pass static check rate        | > 70%                  |
| Implementation | Context efficiency (used/retrieved) | > 70%                  |
| QA             | Defect detection rate               | > 90%                  |
| QA             | False positive rate                 | < 5%                   |
| QA             | Mutation score                      | > 80% (high-risk)      |
| Deployment     | Success rate                        | > 99%                  |
| Deployment     | MTTR                                | < 15 min               |




### Agent-Level


| KPI                  | Formula                                               | Target |
| -------------------- | ----------------------------------------------------- | ------ |
| Attribution Accuracy | `correctly_attributed_failures / total_failures`      | > 85%  |
| Recovery Rate        | `auto_recovered_errors / total_errors`                | > 75%  |
| Tool Call Accuracy   | `correct_tool_calls_first_attempt / total_tool_calls` | > 90%  |
| Hallucination Rate   | `fabricated_facts / total_factual_claims`             | < 5%   |




### Feedback Loop Health


| KPI                  | Metric                                               | Why                                              |
| -------------------- | ---------------------------------------------------- | ------------------------------------------------ |
| Loop trigger rate    | % tasks triggering each named loop                   | High rate on one loop → upstream quality problem |
| Loop resolution rate | % resolving within budget vs. escalating             | Falling rate → platform regression signal        |
| Oscillation rate     | % tasks where same loop fires 2+ times on same issue | FeedbackReport not giving sufficient guidance    |




## L.3 Golden Dataset & Shadow-Mode Graduation

Never trust confidence scores alone to grant autonomy at a risk tier. Shadow-mode graduation: agent proposes → human decides → outcomes compared. A risk tier becomes (semi-)autonomous only after a measured resolution-rate / false-positive threshold is met empirically against the golden dataset.

## L.4 Platform Self-Evaluation

The platform maintains its own regression suite — fixed historical tasks with known outcomes, re-run whenever underlying models, prompts, or agent logic change. Detects *platform regression* separately from a task simply being hard. Distinct from §K (which evaluates the software built — this evaluates the platform itself).

## L.5 DORA Metrics as Business-Facing KPIs

Deployment frequency, lead time for changes, change failure rate, MTTR — bridge from internal agent metrics to how engineering organizations already report on delivery. Computed in Phase 15 from `DeploymentRecord` + incident/rollback data. Not an agent-trajectory metric.

## L.6 Evaluation must be decoupled from orchestration

```
TelemetrySink export + SDLCState + Postgres
        ↓
RunRecord / Trajectory  (packages/evaluation/trajectory.py)
        ↓
EvaluationEngine.evaluate(run)   # no LangGraph import
        ↓
Evaluator[]  →  Score + Evidence
        ↓
EvaluationResult  →  evaluation_results / evaluation_scores
        ↓
Experiment vs Baseline  →  regression gate
```

Evaluators read a **RunRecord**, never a LangGraph `StateGraph` or checkpoint blob. If checkpoint recovery is needed, a loader in `packages/evaluation/loaders/postgres.py` hydrates RunRecord from `tasks`, `cost_tracking`, `hitl_log`, `feedback_loop_events`, `evaluation_results`, Blackboard refs, and exported spans (OTLP JSON or a `span_export` table if added later). The loader is the only place that knows storage layout.

### L.6.1 Canonical evaluation objects

```python
from typing import Literal, TypedDict
from datetime import datetime

class Evidence(TypedDict):
    kind: Literal["metric", "artifact_ref", "span_id", "human_note", "judge_rationale"]
    pointer: str                      # blackboard ref, span_id, or short literal
    detail: str

class Score(TypedDict):
    metric_id: str                    # e.g. "system.cost_usd", "wcp.schema_complete"
    value: float                      # 0–1 for rates; raw for cost/latency
    unit: str
    confidence: float | None          # required for LLM-judge metrics; 1.0 for deterministic
    evidence: list[Evidence]

class EvaluationCase(TypedDict):
    case_id: str
    work_type: str
    repo_fixture: str                 # path under tests/fixtures or golden/
    prompt: str
    expected: dict                    # required_files, acceptance_criteria, known defects
    labels: dict                      # risk_tier, methodology, tags

class EvaluationDataset(TypedDict):
    dataset_id: str
    version: str                      # semver; bump when cases change
    cases: list[EvaluationCase]

class RunRecord(TypedDict):
    """Hydrated after a task (live or golden replay) finishes. Evaluation input."""
    task_id: str
    experiment_id: str | None
    agent_version: str                # git sha of platform
    prompt_version: str               # hash of prompt pack
    model_ids: list[str]
    orchestration_version: str        # git sha; graph topology is not a LangGraph object here
    evaluation_version: str           # evaluator code/config version
    spans_ref: str | None             # optional export pointer
    artifact_refs: list[str]
    outcome: Literal["done", "blocked", "cancelled", "failed"]

class EvaluationResult(TypedDict):
    result_id: str
    task_id: str
    experiment_id: str | None
    scores: list[Score]
    scored_at: datetime

class Experiment(TypedDict):
    experiment_id: str
    name: str
    baseline_experiment_id: str | None
    dataset_id: str
    dataset_version: str
    agent_version: str
    prompt_version: str
    model_ids: list[str]
    notes: str
    created_at: datetime
```

`Evaluator` is a Protocol: `evaluate(run: RunRecord, case: EvaluationCase | None) -> list[Score]`. Implementations live in `packages/evaluation/evaluators/`. No LLM call inside an evaluator unless its `method` is `llm_judge`.

### L.6.2 Evaluation methods — when to use which

| Method | Use when | Examples |
|---|---|---|
| **Deterministic** | Ground-truth exists in state/tools | Schema-valid WCP; ruff/mypy pass; `Task.state`; cost from `cost_tracking`; FL trigger counts; overlap flags from Fan-in events |
| **Reference-based** | Golden case has expected files/tests | Fix Rate vs `expected.required_files`; spec checklist vs `RequirementsSpec.acceptance_criteria` |
| **LLM-as-Judge** | Only when no objective check exists | Decomposition reasonableness; WCP "usefulness"; design coverage narrative |
| **Human** | Irreversible policy, judge calibration, shadow-mode | Graduation (§L.3); judge disagreement review |

Default: deterministic. LLM-as-Judge is opt-in per metric_id, must attach `Evidence.kind="judge_rationale"` and `Score.confidence`. Do not score "reasoning quality" as MVP.

## L.7 Dimension catalog (MVP / Phase 2 / Advanced)

Hierarchy: SYSTEM → PHASE → MANAGER → AGENT → TOOL/ACTION → COMMUNICATION → ENGINEERING OUTCOME.

| Level | Dimension | Method | When |
|---|---|---|---|
| SYSTEM | Task success (`DONE` vs not) | Deterministic | **MVP** |
| SYSTEM | Cost, cycle time, token totals | Deterministic (`cost_tracking`) | **MVP** |
| SYSTEM | HITL count, rollback count | Deterministic | **MVP** |
| SYSTEM | Retry rate, validation fail rate | Deterministic (spans + `feedback_loop_events`) | **MVP** |
| SYSTEM | Recovery rate | Deterministic (FL resolved vs escalate) | **MVP** |
| SYSTEM | Reliability / failure rate | Deterministic | **MVP** |
| SYSTEM | Token efficiency, Fix Rate | Reference + formula (§L.1) | **MVP** |
| PHASE | Phase completed, transition legal (§D.3) | Deterministic | **MVP** |
| PHASE | Handoff packet present / under token cap | Deterministic | Phase 12+ data; **Phase 2** if packets exist |
| PHASE | Unnecessary work (extra loops) | Deterministic counts | **Phase 2** |
| MANAGER | Decomposition covers `ownership_map` files | Deterministic vs RI | **Phase 2** |
| MANAGER | Circular deps rejected | Deterministic | **MVP** (assert on logs from Phase 06 §04 tests) |
| MANAGER | Replan cap honored (≤1 per group) | Deterministic | **MVP** |
| MANAGER | Fan-in never silent-merge | Deterministic (event) | **MVP** |
| AGENT | Scope adherence (`touches_files` ⊆ ownership) | Deterministic | **Phase 2** |
| AGENT | Attribution accuracy | Heuristic (§L.1) | **MVP** |
| AGENT | Output schema (MASC Check 1) | Deterministic | **MVP** |
| TOOL | Call success / timeout | Deterministic (tool_call spans) | **MVP** (once Phase 05 emits them) |
| TOOL | Repeated identical calls | Deterministic | **Phase 2** |
| TOOL | Argument correctness | Reference or judge | **Phase 2** / Advanced |
| COMM | WCP schema complete | Deterministic | **MVP** |
| COMM | Semantic conflict catch (zero file overlap) | Deterministic (Fan-in tests) | **MVP** as integration test; KPI in **Phase 2** |
| COMM | WCP "usefulness" / assumption quality | LLM-judge | **Advanced** |
| OUTCOME | Tests green, QA recommendation | Deterministic (`QAEvidence`) | **MVP** |
| OUTCOME | Requirements satisfaction | Reference + Spec QA | **MVP** where Spec QA exists |
| OUTCOME | Security/maintainability | Tool scores | **Phase 2** (Phase 13 data) |

Trajectory relationship **Decision → Action → Result → Next decision** is reconstructed from parent/child spans + events (§B.8.2). MVP stores it; trajectory-level *scoring* (was this the right sequence?) is **Advanced** — do not block Phase 15 on it.

## L.8 Experiment + baseline loop

```
Baseline Experiment (dataset D vN, platform sha A)
   → Change prompt | model | graph adapter | agent code
   → Same dataset D vN
   → EvaluationEngine
   → Diff scores vs baseline (per metric_id, per case_id)
   → Fail CI if any MVP metric regresses beyond configured epsilon
```

Version fields on every experiment: `agent_version`, `prompt_version`, `model_ids`, `orchestration_version`, `evaluation_version`, `dataset_version`. Attribution of "which component caused the delta" is done by changing **one** of those fields per experiment. Do not change prompts and models in the same experiment if you need attribution.

Shadow-mode graduation (§L.3) is an experiment type whose "expected" is the human decision, not a file diff.

## L.9 Evaluator reliability (Advanced — do not build in Phase 15 MVP)

Judge consistency (same case twice), inter-judge agreement, calibration against human labels. Document as research; ship only after golden dataset has ≥ the sample size used for confidence recalibration. Until then, LLM-judge metrics are unofficial and cannot gate CI.

## L.10 What evaluation consumes vs what it must not

**May read:** `TelemetrySink` exports, `cost_tracking`, `hitl_log`, `feedback_loop_events`, `QAEvidence`, `ImplementationResult`, WCP/ClarificationEscalation lists, Blackboard artifacts, `Task`, golden `EvaluationCase.expected`.

**Must not read:** LangGraph checkpoint internals, `AgentEvent` as a scoring source (UI-only), live model calls except inside an explicit `llm_judge` evaluator, telemetry to *drive* a running task.



# Part M — Prompt Engineering Strategy

Neither prior blueprint specified a prompt engineering strategy beyond "structured outputs." This is a concrete approach for all agents.

## M.1 Output Schema Protocol

Every agent output is a Pydantic schema defined in `agents/prompts/schemas/<agent_id>.py`. MASC Check 1 validates against this schema. Agents are instructed to produce JSON matching the schema — never free-form text for structured outputs.

## M.2 System Prompt Template Structure

```
[ROLE]
You are the [Agent Name]. Your sole responsibility is [narrow scope].
You do NOT [out-of-scope actions].

[CONTEXT INJECTION ORDER]
1. Architecture summary (always injected)
2. Aider repo map for task scope (injected by context builder)
3. Phase Handoff Packet from previous phase
4. Task-specific retrieved context (tool-expanded as needed)

[CONSTRAINTS]
- All outputs must conform to the schema in [schema_ref]
- If confidence in your output is below [threshold], set confidence field accordingly
- Do not proceed if required context is missing — use the get_symbol_signature tool first

[OUTPUT FORMAT]
<JSON schema>
```



## M.3 Reflection Pass (High-Stakes Agents Only)

For Design Manager and Security Architect — after producing initial output, a second LLM call with:

```
"Review your architecture document above. Identify:
1. Any requirement from the spec that is not addressed
2. Any internal contradiction in the design
3. Any assumption that should be explicit

Report findings as a list. If none, state 'No gaps found.'"
```

The reflection output is appended to the draft before it enters `Validator`(design). This improves first-pass validator acceptance rate without requiring a separate agent invocation.

---



# Part N — Production Readiness


| Category        | Risk                                                        | Mitigation                                                                                                                                               |
| --------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Reliability** | Internal scoring/policy failure defaults toward autonomy    | Fail-Closed (Principle 8) — every failure routes toward more oversight                                                                                   |
| **Reliability** | LangGraph checkpointer (PostgreSQL) failure mid-task        | Postgres primary+replica HA; task resumes from last durable checkpoint on failover                                                                       |
| **Reliability** | HITL timeout (human absent)                                 | Configurable timeout → suspend task (never auto-approve); escalation chain                                                                               |
| **Reliability** | Infinite feedback loop                                      | Global `rollback_count` cap; task suspension on breach                                                                                                   |
| **Scalability** | Global knowledge graph bottleneck at 1M+ files              | Federated sharded indexing + global index-of-indices (§G.4)                                                                                              |
| **Scalability** | Sequential design review blocking large migrations          | Parallel sub-design tracks for independent services; single `Validator`(design) at fan-in                                                                |
| **Scalability** | Worker fleet exhaustion under burst load                    | Queue-based backpressure; consumer-group partitioning by risk tier (Critical-risk tasks never starved by Low-risk flood)                                 |
| **SPOF**        | Single model provider (GLM)                                 | Circuit-breaker + checkpoint-and-pause (§I.3)                                                                                                            |
| **SPOF**        | One Postgres instance for checkpointing AND pgvector at MVP | Acceptable early; flagged to split once at-scale repo intelligence lands (different access patterns: read-heavy retrieval vs. write-heavy checkpointing) |
| **SPOF**        | Redis failure (task queue)                                  | Redis Sentinel or Cluster mode                                                                                                                           |
| **Concurrency** | Parallel tasks reading shared RI stores                     | Read/write separation: write → primary, read → replicas                                                                                                  |
| **Concurrency** | Parallel fan-out agents editing overlapping files           | Fan-in conflict-detection node (§D.4)                                                                                                                    |
| **Cost**        | Re-indexing cost at 1M+ files                               | Incremental indexing bounded to changed-file scope; tracked as own cost line                                                                             |
| **Cost**        | Runaway agent retry/decomposition loops                     | Kill-switch (§B.7)                                                                                                                                       |
| **Security**    | Prompt injection via ingested repo/issue/PR content         | Untrusted-content classifier before content enters semantic memory (§B.6)                                                                                |
| **Security**    | Tool supply-chain: compromised linter or MCP server         | Version pinning; least-privilege tool credentials; periodic supply-chain audit (§B.6)                                                                    |
| **Security**    | Sandbox escape during code execution                        | Network-restricted, ephemeral, task-scoped containers, torn down regardless of outcome                                                                   |
| **Operational** | Cannot debug failed run months later                        | Explicit retention: full traces 90 days; episodic outcomes indefinite                                                                                    |
| **Operational** | Policy changes deployed without review                      | Policy configs (§O directory) go through same PR review process as code                                                                                  |


---



# Part O — Technology Stack


| Category                 | Recommendation                      | Version       | Reason                                                |
| ------------------------ | ----------------------------------- | ------------- | ----------------------------------------------------- |
| **Language**             | Python                              | 3.12          | Modern async, type system, ecosystem                  |
| **Orchestration**        | LangGraph + LangChain core          | 0.3+          | Mandated; native HITL, checkpointing, streaming       |
| **Durable state**        | LangGraph Postgres checkpointer     | —             | Per §D                                                |
| **API framework**        | FastAPI                             | 0.111+        | Async-native; matches LangGraph's execution model     |
| **Job queue**            | Redis Streams (primary) or RabbitMQ | —             | Consumer-group partitioning for risk-tier isolation   |
| **Worker framework**     | ARQ (if Redis)                      | 0.25+         | Async; mature backpressure and retry semantics        |
| **Primary database**     | PostgreSQL                          | 16            | Checkpointing, Task records, audit log, approvals     |
| **Vector search**        | pgvector → Qdrant                   | 0.7+ → latest | pgvector at MVP (reuses Postgres); Qdrant at scale    |
| **Graph database**       | NetworkX → Neo4j                    | — → 5.x       | NetworkX: MVP, zero infra; Neo4j: multi-hop Cypher    |
| **Code search**          | Zoekt (trigram)                     | latest        | Battle-proven at Sourcegraph scale                    |
| **AST parsing**          | Tree-sitter                         | 0.23+         | Multi-language; fast incremental                      |
| **Deep security**        | CodeQL                              | latest        | Dataflow analysis; periodic deep scans                |
| **Inline security**      | Semgrep                             | 1.70+         | Fast pattern-based; runs inline during QA             |
| **Dependency audit**     | pip-audit + OSV-Scanner / Trivy     | latest        | CVE + license scanning                                |
| **Mutation testing**     | mutmut (Python) / Stryker (JS)      | 2.5+          | High-risk, critical-path modules only                 |
| **Property testing**     | Hypothesis                          | 6.100+        | Pure functions and parsers                            |
| **API fuzzing**          | schemathesis                        | 3.27+         | OpenAPI-based contract testing                        |
| **Load testing**         | k6 / Locust                         | latest        | Performance QA for High+ risk                         |
| **UI testing**           | Playwright                          | 1.44+         | Browser automation for UI QA                          |
| **Accessibility**        | axe-core                            | latest        | WCAG 2.1 compliance                                   |
| **Caching**              | Redis                               | 7.2+          | Hot RI query results; UI session state                |
| **HTTP client**          | httpx                               | 0.27+         | Async; HTTP/2                                         |
| **Model adapters**       | LangChain BaseChatModel             | 0.3+          | Structured output, tools, streaming for free          |
| **LiteLLM**              | Optional normalization layer        | latest        | If GLM endpoint has OpenAI compatibility gaps         |
| **Tracing**              | OpenTelemetry SDK                   | 1.25+         | Implements `TelemetrySink` only; OTLP export          |
| **Agent observability**  | Langfuse (self-hosted, optional)    | 2.x           | OTLP backend for humans — not the eval contract       |
| **Metrics**              | Prometheus                          | 2.52+         | System and agent metrics                              |
| **Dashboards**           | Grafana                             | 10.x          | KPI dashboards; alerting                              |
| **Logging**              | structlog                           | 24.x          | Structured JSON; same OTel pipeline                   |
| **Secrets scanning**     | detect-secrets                      | 1.5+          | Pre-commit + CI                                       |
| **Linting / formatting** | ruff                                | 0.4+          | Replaces flake8 + black + isort                       |
| **Type checking**        | mypy                                | 1.10+         | Static type validation                                |
| **Testing**              | pytest + pytest-asyncio             | 8.2+          | Async test support                                    |
| **Package management**   | uv                                  | 0.2+          | Faster than pip/poetry                                |
| **MCP client**           | mcp Python SDK                      | 1.x           | Official client                                       |
| **Auth (human UI)**      | OAuth2/OIDC (org identity provider) | —             | Human-facing auth; separate from agent service tokens |
| **IaC / deployment**     | Terraform (or org standard)         | —             | All provisioning; never direct agent-to-cloud         |


---



# Part P — UI Specification

12 screens. Each is a thin read layer over objects already defined in this document. No new backend data model.


| Screen                         | Shows                                                                                                                                      | Data Source                                    |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------- |
| **1. New Task**                | Intake form (free text + optional structured fields)                                                                                       | — (write path only)                            |
| **2. Requirement Interview**   | Current question from Questioning Engine (§E.4), **plus questions auto-answered from repo with their retrieved answers shown**             | RequirementsSpec, RI responses                 |
| **3. Workflow Overview**       | WorkflowProfile in plain language — risk tier, methodology, active agents, and *which §F.3 rule fired*                                     | Task, WorkflowProfile                          |
| **4. SDLC Phase View**         | Current position in the state machine (§D.3); backward edges shown as visually distinct loops                                              | `Task.state` + `agent_events` phase transitions (§D.2.1) |
| **5. Active Agents**           | Which agents are running now and their current tool call                                                                                   | OTel trace stream                              |
| **6. Live Execution Timeline** | Phase transitions, feedback loops triggered, approvals — chronological                                                                     | agent_events channel                           |
| **7. Questions Queue**         | Open questions across a human's in-flight tasks, with already-gathered context shown                                                       | hitl_queue where request_type="clarification"  |
| **8. Human Approval Requests** | Evidence bundle (diff, QA summary, confidence breakdown, precedent tasks), decision buttons, timeout countdown                             | ApprovalGate evidence_bundle_spec, HITLRequest |
| **9. Agent Logs**              | Raw OTel trace detail per agent                                                                                                            | Trace backend                                  |
| **10. QA Summary**             | Which QA checks ran (§K.1 matrix), results, bug reproduction result first for bug/hotfix                                                   | QAEvidence                                     |
| **11. Deployment Status**      | Strategy, pipeline URL, canary traffic split + health comparison chart, auto-promote/rollback thresholds                                   | DeploymentRecord, health metrics               |
| **12. Final Report**           | Definition-of-Done checklist per work type (§A's B.11 equivalent), cost breakdown, HITL history, files changed, ADRs generated, KPI scores | Full task record                               |




### WebSocket Event Protocol

```python
class AgentEvent(TypedDict):
    event_id: str
    task_id: str
    timestamp: str
    agent_id: str
    phase: str
    span_id: str | None               # correlates to TelemetrySink span (§B.8); UI-only
    parent_span_id: str | None
    event_type: Literal[
        "agent_started", "agent_tool_call", "agent_tool_result",
        "agent_token_stream", "agent_completed", "agent_failed",
        "masc_flag", "hitl_required", "hitl_responded",
        "phase_completed", "task_completed",
        "rollback_initiated", "feedback_loop_triggered",
        "worker_coordination_packet_emitted", "clarification_escalated",
        "clarification_resolved", "fan_in_replan_triggered", "task_cancelled"
    ]
    payload: dict
```

`AgentEvent` is **strictly observational** — a projection of `TelemetrySink` spans/events plus already-committed state changes, for the UI and audit logs. It is not an evaluator input (§L.10).

**Hard rule:** no graph node, Manager, Fan-in Coordinator, Validator, or policy function may read `AgentEvent` or `SDLCState.agent_events` to decide routing, scheduling, planning, or replanning. Events are write-only from the orchestration layer's perspective. Control-flow inputs are exclusively:

- `SDLCState` typed channels (`requirements`, `task_decomposition`, `worker_coordination_packets`, `clarification_escalations`, `feedback_reports`, etc.)
- Validator / MASC outputs
- Repository Intelligence tool results
- Workflow Policy Engine (`resolve_workflow_profile`, `escalate_model_tier`)
- Manager decisions over the above

This is the same discipline as §D.9.1's rule for `messages` — observability channels must never become control channels.

---



# Part Q — Project Structure

```
sdlc-platform/
├── apps/
│   ├── api/                      # FastAPI service (REST + WebSocket)
│   └── worker/                   # LangGraph execution workers (ARQ)
│
├── packages/
│   ├── common/                   # Shared: Task model, config, security utils
│   │   ├── telemetry.py          # TelemetrySink Protocol (§B.8.3) — no OTel import
│   │   └── tracing.py            # OtelTelemetrySink + structlog correlation
│   │
│   ├── orchestration/            # LangGraph graphs, nodes, state schemas
│   │   ├── state.py              # SDLCState TypedDict + all reducers
│   │   ├── dag_constructor.py    # Single orchestrator StateGraph; WorkflowProfile flags drive conditional edges (§D.2)
│   │   ├── telemetry_adapter.py  # LangGraph → TelemetrySink only (§B.8.5)
│   │   ├── feedback.py           # FeedbackReport schema + loop registry
│   │   ├── masc.py               # MASCEngine (3-check pipeline)
│   │   ├── intent_tracker.py     # IntentTracker
│   │   ├── checkpointers/
│   │   │   └── postgres.py       # AsyncPostgresSaver + thread_id[:255]
│   │   └── workflow_profiles/    # WorkflowProfile preset configs — NOT separate LangGraph graphs (§D.2)
│   │       ├── conservative.py   # mirrors WorkflowProfile.most_conservative()
│   │       ├── standard.py
│   │       ├── hotfix.py         # hotfix fast-path flags
│   │       └── enterprise.py
│   │
│   ├── agents/
│   │   ├── base.py               # BaseAgent (retry, MASC, TelemetrySink spans)
│   │   ├── templates/
│   │   │   ├── approval_gate.py  # ApprovalGate template
│   │   │   └── validator.py      # Validator template
│   │   ├── intake/
│   │   │   └── planning_manager.py
│   │   ├── requirements/
│   │   │   ├── requirements_analyst.py
│   │   │   └── confidence_scorer.py
│   │   ├── design/
│   │   │   ├── design_manager.py
│   │   │   ├── repo_architecture_analyst.py
│   │   │   └── security_architect.py
│   │   ├── implementation/
│   │   │   ├── implementation_manager.py
│   │   │   ├── codegen_agent.py       # Instanced via Send API
│   │   │   └── feedback_agent.py
│   │   ├── qa/
│   │   │   ├── qa_manager.py
│   │   │   ├── bug_validation_agent.py
│   │   │   ├── dependency_impact_agent.py
│   │   │   ├── spec_qa_agent.py
│   │   │   └── suite_runner.py        # QA tool orchestrator
│   │   ├── release/
│   │   │   ├── review_manager.py
│   │   │   ├── release_manager.py
│   │   │   ├── rollback_agent.py
│   │   │   └── monitoring_manager.py
│   │   └── prompts/
│   │       ├── system/               # System prompt templates per agent
│   │       └── schemas/              # Pydantic output schemas per agent
│   │
│   ├── requirements_engine/      # Dynamic Questioning Engine (§E.4)
│   │   ├── engine.py
│   │   └── models.py             # Question, IntentDiff schemas
│   │
│   ├── repo_intel/               # Repository Intelligence service (§G)
│   │   ├── api.py                # RepositoryIntelligence public interface
│   │   ├── indexers/
│   │   │   ├── coordinator.py    # Sharded parallel indexer
│   │   │   ├── treesitter.py
│   │   │   ├── zoekt_client.py
│   │   │   └── incremental.py    # Git hook integration
│   │   ├── graph/
│   │   │   ├── networkx_client.py  # MVP graph
│   │   │   ├── neo4j_client.py     # Scale graph
│   │   │   └── bfs.py
│   │   ├── vector/
│   │   │   ├── pgvector_client.py
│   │   │   ├── qdrant_client.py
│   │   │   └── hybrid_retrieval.py # RRF fusion
│   │   └── summaries/
│   │       ├── architecture_summary.py  # AST-generated, never LLM
│   │       └── repo_map.py              # Aider-style PageRank map
│   │
│   ├── context_engine/           # Context engineering (§H)
│   │   ├── budget.py             # ContextBudget per phase
│   │   ├── builder.py            # Progressive context loading
│   │   ├── compressor.py         # 5-step compression pipeline
│   │   └── handoff_packet.py     # PhaseHandoffPacket
│   │
│   ├── model_adapters/           # Model abstraction layer (§I)
│   │   ├── base.py               # ModelAdapter Protocol
│   │   ├── router.py             # ModelRouter + escalate_model_tier
│   │   ├── registry.py
│   │   ├── glm/
│   │   │   └── adapter.py        # GLM-4.7 + GLM-4.7-Flash
│   │   └── telemetry.py          # UsageTelemetry → TelemetrySink llm_call spans + BudgetTracker
│   │
│   ├── workflow_engine/          # Routing rules (§F)
│   │   ├── policy.py             # resolve_workflow_profile()
│   │   └── context.py            # WorkflowContext schema
│   │
│   ├── mcp_integrations/         # MCP clients + adapters (§J)
│   │   ├── base.py
│   │   ├── idempotency.py
│   │   ├── clients/
│   │   │   ├── github.py
│   │   │   ├── jira.py
│   │   │   └── slack.py
│   │   └── adapters/             # Custom adapters for missing MCP servers
│   │
│   ├── qa/                       # QA tool wrappers (§K)
│   │   ├── static_analysis.py
│   │   ├── security_qa.py
│   │   ├── mutation_runner.py
│   │   ├── property_tester.py
│   │   └── evidence_collector.py
│   │
│   ├── evaluation/               # Evaluation framework (§L) — no LangGraph imports
│   │   ├── engine.py             # EvaluationEngine
│   │   ├── pipeline.py           # post-task score() ARQ job
│   │   ├── trajectory.py         # RunRecord hydration helpers
│   │   ├── loaders/
│   │   │   └── postgres.py       # tasks + cost + hitl + FL events → RunRecord
│   │   ├── evaluators/           # Evaluator Protocol implementations
│   │   ├── fix_rate.py
│   │   ├── attribution.py
│   │   ├── feedback_loop_health.py
│   │   ├── experiments.py        # baseline diff, CI gate
│   │   └── benchmarks/
│   │       ├── golden_dataset.py
│   │       └── shadow_mode.py
│   │
│   └── memory/                   # 4-tier memory stores (§B.3)
│       ├── working/              # LangGraph state (managed by orchestration/)
│       ├── episodic/             # Postgres + pgvector
│       ├── semantic/             # RI service (managed by repo_intel/)
│       └── procedural/           # Configs (managed by configs/)
│
├── ui/                           # React + TypeScript SPA (§P)
│   └── src/
│       ├── screens/              # 12 screens
│       ├── components/
│       ├── hooks/                # useWebSocket, useTask, useHITL
│       └── api/                  # Typed API client
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/                 # Adapter interface contract tests
│   ├── benchmark/                # Golden dataset, retrieval precision, seeded defects
│   └── chaos/                    # Induced-failure verification (§N)
│
├── configs/                      # Versioned, PR-reviewed (§N)
│   ├── workflow_policies/        # §F rule sets
│   ├── pricing/                  # §I pricing registry
│   └── question_bank/            # §E.4 question bank
│
├── db/
│   ├── migrations/               # Alembic
│   └── schema.sql                # Initial schema
│
├── scripts/
│   ├── init_db.py
│   ├── index_repo.py
│   └── post_commit_hook.sh
│
├── docker-compose.yml            # PostgreSQL + Redis + Langfuse (dev)
├── docker-compose.prod.yml
├── pyproject.toml                # uv dependencies
├── Makefile
└── .env.example
```

---



# Part R — Database Schema (Core Tables)

```sql
-- LangGraph-managed: checkpoints, checkpoint_blobs, checkpoint_writes

-- Platform-managed:

CREATE TABLE tasks (
    id              VARCHAR(255) PRIMARY KEY,  -- ≤ 255 chars, enforced at Task model
    title           TEXT NOT NULL,
    source          VARCHAR(50) NOT NULL,
    type            VARCHAR(50) NOT NULL,
    methodology     VARCHAR(50) NOT NULL,
    risk_tier       VARCHAR(20) NOT NULL,
    confidence_score FLOAT,
    state           VARCHAR(50) DEFAULT 'intake',
    workflow_profile_id VARCHAR(255),
    token_ceiling   INTEGER DEFAULT 2000000,
    cost_ceiling_usd FLOAT DEFAULT 20.0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    created_by      VARCHAR(255)
);

CREATE TABLE approvals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         VARCHAR(255) REFERENCES tasks(id),
    checkpoint      VARCHAR(100) NOT NULL,
    approver        VARCHAR(255),
    decision        VARCHAR(50),
    evidence_ref    TEXT,         -- Blackboard pointer
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    decided_at      TIMESTAMPTZ
);

CREATE TABLE hitl_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         VARCHAR(255) REFERENCES tasks(id),
    request_type    VARCHAR(50) NOT NULL DEFAULT 'approval'
                    CHECK (request_type IN ('clarification', 'approval', 'policy_review', 'risk_approval')),
    phase           VARCHAR(100),
    reason          TEXT,
    evidence_ref    TEXT,
    options         JSONB,
    response        TEXT,
    responded_by    VARCHAR(255),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    responded_at    TIMESTAMPTZ,
    timeout_at      TIMESTAMPTZ NOT NULL
);

CREATE TABLE cost_tracking (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         VARCHAR(255) REFERENCES tasks(id),
    agent_id        VARCHAR(255),
    phase           VARCHAR(100),
    model_id        VARCHAR(100),
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    cost_usd        NUMERIC(10,6),
    latency_ms      INTEGER,
    recorded_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE evaluation_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         VARCHAR(255) REFERENCES tasks(id),
    experiment_id   UUID,
    fix_rate        FLOAT,
    token_efficiency FLOAT,
    hitl_count      INTEGER,
    rollback_count  INTEGER,
    cycle_time_s    INTEGER,
    cost_usd        NUMERIC(10,6),
    attribution_accuracy FLOAT,
    recorded_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE evaluation_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id       UUID REFERENCES evaluation_results(id),
    task_id         VARCHAR(255) REFERENCES tasks(id),
    metric_id       VARCHAR(200) NOT NULL,
    value           FLOAT NOT NULL,
    unit            VARCHAR(50),
    confidence      FLOAT,
    evidence        JSONB,
    recorded_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE evaluation_experiments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    baseline_id     UUID,
    dataset_id      VARCHAR(255) NOT NULL,
    dataset_version VARCHAR(50) NOT NULL,
    agent_version   VARCHAR(64),
    prompt_version  VARCHAR(64),
    model_ids       JSONB,
    orchestration_version VARCHAR(64),
    evaluation_version VARCHAR(64),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE regression_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_path     VARCHAR(500),
    failure_type    VARCHAR(100),
    fix_pattern     TEXT,
    task_id         VARCHAR(255) REFERENCES tasks(id),
    recorded_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE design_decisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    adr_id          VARCHAR(100) UNIQUE,
    module_paths    JSONB,
    decision        TEXT,
    rationale       TEXT,
    task_id         VARCHAR(255) REFERENCES tasks(id),
    recorded_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(255) UNIQUE NOT NULL,
    role            VARCHAR(50) NOT NULL DEFAULT 'developer',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE feedback_loop_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         VARCHAR(255) REFERENCES tasks(id),
    loop_id         VARCHAR(100),          -- e.g., "FL-04"
    source_agent    VARCHAR(255),
    target_agent    VARCHAR(255),
    attempt_number  INTEGER,
    resolved        BOOLEAN,
    recorded_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_tasks_state        ON tasks(state);
CREATE INDEX idx_tasks_risk_tier    ON tasks(risk_tier);
CREATE INDEX idx_cost_task_id       ON cost_tracking(task_id);
CREATE INDEX idx_eval_scores_metric ON evaluation_scores(metric_id);
CREATE INDEX idx_hitl_request_type  ON hitl_log(request_type) WHERE responded_at IS NULL;
CREATE INDEX idx_regression_module  ON regression_history(module_path);
CREATE INDEX idx_design_modules     ON design_decisions USING GIN(module_paths);
CREATE INDEX idx_feedback_task      ON feedback_loop_events(task_id, loop_id);
```

---



# Part S — RBAC Model


| Role        | Description                                                                     |
| ----------- | ------------------------------------------------------------------------------- |
| `developer` | Can submit tasks, view execution, respond to clarification questions            |
| `reviewer`  | developer + can approve design and implementation HITL gates                    |
| `deployer`  | reviewer + can approve deployment HITL gates and trigger rollbacks              |
| `admin`     | Full access: modify RBAC, view cost data, suspend tasks, modify risk thresholds |



| Action                          | developer | reviewer | deployer | admin |
| ------------------------------- | --------- | -------- | -------- | ----- |
| Submit task                     | ✓         | ✓        | ✓        | ✓     |
| View execution / logs           | ✓         | ✓        | ✓        | ✓     |
| Respond to clarification        | ✓         | ✓        | ✓        | ✓     |
| Approve scope / design HITL     | ✗         | ✓        | ✓        | ✓     |
| Approve release HITL            | ✗         | ✓        | ✓        | ✓     |
| Approve deployment (staging)    | ✗         | ✓        | ✓        | ✓     |
| Approve deployment (production) | ✗         | ✗        | ✓        | ✓     |
| Trigger rollback                | ✗         | ✗        | ✓        | ✓     |
| View cost data                  | ✗         | ✗        | ✗        | ✓     |
| Suspend tasks                   | ✗         | ✗        | ✗        | ✓     |
| Modify risk thresholds          | ✗         | ✗        | ✗        | ✓     |


---



# Part T — Priority Summary



## P0 — Must Ship (MVP)

- Task data model + PostgreSQL schema (Phase 0)
- `SDLCState` TypedDict + all reducers (Phase 0)
- Cost kill-switch + execution sandbox (Phase 0)
- `AsyncPostgresSaver` + `thread_id[:255]` enforcement (Phase 1)
- `ModelAdapter` ABC + GLM adapter + pricing registry (Phase 2)
- Tree-sitter symbol index + Zoekt search + pgvector + incremental indexing (Phase 3)
- Dynamic Requirements Questioning Engine (Phase 4)
- Planning Manager + Requirements Analyst + Confidence Scorer + `Validator`(requirements) (Phase 5)
- `interrupt()` HITL gates + `ApprovalGate` template (Phase 8)
- MASC engine (3-check pipeline) (runs from Phase 5 onward)
- `TelemetrySink` + OTel adapter (failure-isolated) (Phase 0)
- FastAPI + WebSocket event streaming (Phase 8)
- UI Screens 1–4, 7–8 (Phase 9)



## P1 — Q1 Post-MVP

- Design phase: Design Manager + Repo Architecture Analyst + Security Architect + `Validator`(design) (Phase 6)
- Implementation phase: Manager + CodeGen sub-agents + Feedback Agent + Integration Validator (Phase 6)
- QA phase: full pipeline with risk routing + Bug Validation Agent (Phase 7)
- Release phase: Review Manager + Release Manager + Rollback sub-agent + Monitoring Manager (Phase 8)
- Workflow Policy Engine: `resolve_workflow_profile()` + `escalate_model_tier()` (Phase 10)
- NetworkX → Neo4j graph migration (Phase 11)
- Phase Handoff Packets + context compression pipeline (Phase 12)
- Semgrep (inline QA) + mutmut + Hypothesis (Phase 13)
- GitHub MCP + Jira MCP + Slack MCP (Phase 14)
- EvaluationEngine + RunRecord loaders + MVP KPIs + experiment/baseline CI (Phase 15)
- RBAC enforcement + audit log
- UI Screens 5–6, 9–11 (Phase 9)



## P2 — Q2

- Aider-style PageRank repo map (Phase 12)
- CodeQL periodic deep scans (Phase 13)
- Performance QA (k6/Locust) + Accessibility QA (axe-core) + API contract fuzzing (schemathesis) (Phase 13)
- GitLab MCP + custom adapter base (Phase 14)
- Golden dataset + shadow-mode graduation harness (Phase 15; can start assembling cases earlier)
- LLM-as-Judge evaluators behind `Evaluator` protocol (optional; not CI-gating)
- Platform self-evaluation regression suite (Phase 15)
- pgvector → Qdrant migration (Phase 16)
- UI Screen 12 (Phase 9)
- Production hardening + chaos tests (Phase 16)



## P3 — Future

- Multi-provider model routing (Anthropic, OpenAI, DeepSeek)
- Multi-repo federated RI across organizations
- Fine-tuned Intent Classifier and CodeGen sub-agents (where justified by §E.3)
- Kubernetes horizontal scaling for worker pool
- Autonomous technical debt scheduling
- Self-improving evaluation (evaluation model trained on human-shadow-mode comparisons)
- Temporal as durability backbone for very long-running tasks (multi-day spans)

---

*Implementation starts at §B.1 (Task Data Model), §B.4 (Confidence Model), §A.2 Principle 8 (Fail-Closed), and §E.1 (Agent Templates). Everything from §F onward assumes those four exist and are correctly wired. Three things to verify against live documentation before implementation: GLM's OpenAI-compatibility (§I.1), current MCP server maturity for Azure DevOps and GitLab (§J.1), and whether your repositories have clean existing shard boundaries or will need manual definition (§G.4).*