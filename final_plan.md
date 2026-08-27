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
| **Requirements Engine**     | Detailed question de;pendency graph, auto-skip via repo context, confidence-gated exit           | Same design, called "Dynamic Questioning Engine," as a dedicated phase and package                                                                   | **Combined.** V2's question dependency graph is more detailed; AI-Native's promotion to a first-class phase and package is the right architectural signal. V3 adopts both                                                                                                           |
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


## 0.3 Revision 3.1 — Development-Phase Execution Topology

V3.0 specified the Development (Design + Implementation) phase as **parallel-first**: the Implementation Manager decomposes work and (in V3.0) fans out N concurrent CodeGen workers via `Send`, closed by a deterministic Fan-in Coordinator. Revision 3.1 generalizes this to **runtime-selected execution topology** — parallel, sequential, or hybrid — for the Development phase only, and moves mechanical `Send` exclusively to the Wave Scheduler (§D.9.5). No other phase changes.

The change is small in *shape*: V3.0 already fanned out CodeGen workers. What V3.0 lacked was a first-class `ExecutionPlan` (waves + `max_wave_width` + derived `topology_class`) and a deterministic planner. `TaskDecomposition.execution_order` is **removed** — the Manager must not emit a schedule.

| #   | Decision | Rationale |
| --- | -------- | --------- |
| 7   | **One wave-based executor, not three topology modes** (§D.10.1) | Parallel = one wave of width N. Sequential = N waves of width 1. Hybrid = anything else. `topology_class` is a *derived label*, never an input that switches code paths. Three executors would mean three fan-in semantics, three retry paths, three sets of bugs. |
| 8   | **Topology is chosen by a deterministic function over a dependency graph, not by an LLM** (§D.10.3) | Principle 5 applied to scheduling. The Manager (LLM) decides *what* the sub-tasks are; `plan_execution_waves()` (pure, unit-testable) decides *when* each runs. Matches the precedent set by `resolve_workflow_profile()` (§F.3). |
| 9   | **Parallelism is a function of subtask independence, not task complexity** (§D.10.2) | Complexity enters only indirectly — a harder task yields more sub-tasks with more dependency edges, which naturally produces a deeper, narrower wave DAG. There is no "complex → sequential" rule anywhere in the design. |
| 10  | **Plan width is separated from dispatch concurrency** (§D.10.4) | The plan states which sub-tasks *may* run together; runtime backpressure decides how many actually run at once. This keeps the plan reproducible (required for golden-dataset evaluation, §L.8) while still respecting fleet capacity. |
| 11  | **Plan amendment (deterministic, cheap) is distinguished from replan (LLM, bounded)** (§D.10.5) | A runtime-discovered dependency that only constrains *not-yet-dispatched* sub-tasks is resolved by re-levelizing the graph — no model call, no Manager pass. Only a broken decomposition escalates to a bounded Manager replan. Without this split, "adaptive topology" would be an unbounded cost feature. |
| 12  | **Amendments may only narrow, never widen** (§D.10.5) | Each amendment strictly adds blocking edges, so the amendment loop provably terminates (edge count is bounded by n²) and the audit trail never has to explain a decision to re-parallelize work it had already serialized. |
| 13  | **WCP is retained and generalized, not replaced** (§D.9.2) | WCP was *motivated* by parallelism, but its payload (discovered dependencies, interface changes, touched files) is topology-independent — and is strictly *more* load-bearing under sequential/hybrid execution, because it is the mechanism by which wave K's discoveries reach wave K+1. Two fields added (`wave_index`, `plan_version`); nothing removed. |
| 14  | **`WaveHandoffNote` — intra-phase handoff, assembled deterministically** (§D.10.6) | The sequential/hybrid analogue of `PhaseHandoffPacket`. Assembled by the Fan-in Coordinator by union/dedup/truncate over completed WCPs — still zero LLM calls in Fan-in. This is the *only* new communication artifact, and it is a projection of existing state, not a new channel. |
| 15  | **Worker→worker communication remains forbidden in every topology** (§D.9.1) | Sequential execution raises the temptation ("A is done, just hand B its output"). That is precisely what a `WaveHandoffNote` does — with provenance, a token cap, and a conflict check. A direct channel would add nondeterminism, unbounded context growth, and a deadlock class that currently cannot exist. |
| 16  | **Worker-spawned sub-agents rejected for MVP and Phase 2; bounded delegation is evidence-gated** (§D.10.8) | The problem it would solve (a sub-task too large for one worker) is already solved at zero architectural cost: the worker raises `ClarificationEscalation(category="scope_ambiguity")` and the Manager re-decomposes into the next wave. |
| 17  | **Context Ledger — critical facts are never compressed, because they are never in the compressible tier** (§H.5) | Rather than hoping a summarizer preserves decisions and constraints, they are extracted into a small, typed, append-only fact table with provenance pointers. Compression operates on the raw trajectory; the ledger is lossless by construction. |
| 18  | **TP policy is two-phase: hard gates then soft min-caps** (§D.10.3) | First-match exclusive hard gates force width=1 when independence cannot be trusted. Soft caps then take `min(...)` of all matching conservatism rules and `WorkflowProfile`/`WorkflowContext` bounds. Removes undefined `manager_suggestion` and the CRITICAL width contradiction. |
| 19  | **Active `ExecutionPlan` ≠ historical execution record** (§D.4.4) | Demotion rewrites the *active* remaining schedule. Telemetry/`topology_decisions` retain what was attempted. Never leave a conflicting `[A,B]` wave as a live re-executable plan entry. |
| 20  | **Wave demotion: supersede-all-conflict-members, then serialize by deterministic order** (§D.4.4) | No silent winner-merge of a conflicting pair. Both (all) conflict members are superseded; a total order is computed; blocking edges are added; remaining plan is amended; redispatches use integration HEAD after each successful predecessor merge. |
| 21  | **Send is issued only by Wave Scheduler; Managers own coordination authority** (§D.9.5) | Manager decides WHAT and may replan. Topology Selector decides WHEN. Wave Scheduler is the sole graph node allowed to return `Send` for CodeGen. Workers never dispatch. |
| 22  | **Implementation-phase LLM budget: one Manager structured call; topology is Python** (§D.10.11) | Four named layers must not imply four model calls. Happy-path extra LLMs vs V3.0: **zero**. Manager does not ReAct-query RI. Selector does bounded deterministic RI. TP rules are config-driven deterministic policy, never an LLM. |

**Terminology introduced in 3.1 (used consistently across every document):** `ExecutionPlan`, `ExecutionWave`, `wave_index`, `plan_version`, `topology_class`, `SubtaskDependencyGraph` (SDG), `TopologyDecisionRecord`, `WaveHandoffNote`, `plan amendment` vs. `replan`, `wave demotion`, `Context Ledger`, `hard gate` vs. `soft cap` (TP rules).

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
9. **Intentional worker isolation.** Concurrently-running workers are deliberately unaware of each other. Cross-worker knowledge is delayed until Fan-in, never exchanged mid-flight. This is not a limitation — it is what preserves determinism, auditability, reproducibility, reasoning quality, deadlock avoidance, and safe parallelism at scale. The communication invariant (§D.9.1) is the operational expression of this principle; Fan-in is where intentional cross-branch knowledge is first assembled. **This principle is topology-independent (§D.10):** under sequential and hybrid execution, a later worker receives an earlier worker's findings through the `WaveHandoffNote` assembled at Fan-in (§D.10.6) — never through a direct channel, and never by reading another worker's in-flight state.
10. **Execution shape follows dependency structure, not difficulty.** How much of the Development phase runs in parallel is determined by measured independence between sub-tasks — file, symbol, interface, and shared-resource dependencies read from Repository Intelligence — never by a judgment that a task "feels complex." The scheduling decision itself is a deterministic, unit-testable function (§D.10.3), consistent with Principle 5.



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
    decision: str            # approve | reject_with_feedback | request_changesSun
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
    """WHAT the work is. Produced by the Implementation Manager (LLM). It states the
    sub-tasks, their scopes, and their *declared* dependencies. It does NOT decide the
    schedule — that is `ExecutionPlan`, produced deterministically from this by
    `plan_execution_waves()` (§D.10.3)."""
    tasks: list[dict]                 # [{id, description, module, target_files, declared_dependencies, model_tier_hint}]
    ownership_map: dict[str, str]     # {module_path: subtask_id}
    version: int                      # incremented on every Manager replan (§D.10.5)
    # V3.0 `execution_order` is REMOVED. Do not emit it. The scheduler ignores any leftover field.

class SubtaskDependencyEdge(TypedDict):
    """One typed, evidence-bearing reason why two sub-tasks are related. Every edge cites
    where it came from — there are no unsourced edges, because an unsourced edge cannot be
    audited or evaluated for 'was this serialization necessary?' (§L.7)."""
    from_subtask: str
    to_subtask: str                   # from_subtask must complete before to_subtask
    kind: Literal[
        "produces_interface",         # to_ consumes a symbol from_ creates/changes
        "file_overlap",               # both claim the same file
        "symbol_overlap",             # both claim the same symbol
        "shared_resource",            # same DB entity, migration, proto, config, lockfile
        "build_order",                # generated/compiled artifact ordering
        "test_coupling",              # shared fixture or suite
        "declared",                   # Manager asserted it; not yet RI-verified
        "discovered",                 # added at runtime from a WCP or escalation (§D.10.5)
    ]
    blocking: bool                    # True → forces wave ordering. False → advisory only.
    evidence: str                     # RI query name + result digest, or WCP/escalation id
    source: Literal["manager_declared", "repo_intelligence", "runtime_discovery"]
    confidence: float                 # 1.0 for deterministic RI/structural facts

class SubtaskDependencyGraph(TypedDict):
    """Nodes are subtask_ids from TaskDecomposition; edges are SubtaskDependencyEdge.
    Built once per plan_version, amended incrementally (§D.10.5). Never rebuilt from a
    full repository scan — see §D.10.7's query budget."""
    nodes: list[str]
    edges: list[SubtaskDependencyEdge]
    plan_version: int
    ri_available: bool                # False → Fail-Closed to fully sequential (§D.10.9)

class ExecutionWave(TypedDict):
    """One dispatch group. All members are mutually independent under the blocking edges
    of the SDG at this plan_version."""
    wave_index: int                   # 0-based, monotonic within a plan_version
    subtask_ids: list[str]
    width: int                        # len(subtask_ids); 1 == this wave is sequential
    rationale: str                    # why these are co-scheduled / why the wave was split

class ExecutionPlan(TypedDict):
    """WHEN the work runs. The single object that expresses parallel, sequential, and
    hybrid execution — there is no separate 'mode'. Produced by plan_execution_waves()
    (§D.10.3); consumed by the Wave Scheduler node (§D.4.0)."""
    plan_version: int
    task_id: str
    waves: list[ExecutionWave]
    topology_class: Literal["sequential", "parallel", "hybrid"]  # DERIVED, never an input
    max_wave_width: int               # policy cap actually applied (§D.10.4)
    dispatch_concurrency: int         # runtime cap; ≤ max_wave_width. Does NOT change plan shape.
    dependency_graph: SubtaskDependencyGraph
    created_from: Literal["initial_plan", "amendment", "replan"]
    superseded_plan_version: int | None

class TopologyDecisionRecord(TypedDict):
    """Why this plan has this shape. Written once per plan_version. Evaluation (§L.7)
    scores this object. UI: Screen 6 timeline + Screen 3 profile; there is no Screen 13."""
    decision_id: str
    task_id: str
    plan_version: int
    topology_class: Literal["sequential", "parallel", "hybrid"]
    subtask_count: int
    wave_count: int
    widths: list[int]                             # width per wave
    blocking_edge_count: int
    advisory_edge_count: int
    features: dict                                # static feature snapshot (§D.10.2 Tier A)
    policy_rules_fired: list[str]                 # e.g. ["TP-08"] or ["TP-03"]
    width_cap_source: str                         # canonical string, see §D.10.3 final-width formula
    fail_closed_reason: str | None                # set when RI/feature collection failed
    created_from: Literal["initial_plan", "amendment", "replan"]
    created_at: datetime

class WaveHandoffNote(TypedDict):
    """Intra-phase handoff: what waves 0..K produced that wave K+1 must know. The sequential/
    hybrid analogue of PhaseHandoffPacket (§B.5). Assembled DETERMINISTICALLY by the Fan-in
    Coordinator (union → dedup → priority-truncate over completed WCPs) — Fan-in still makes
    zero model calls (§D.4.1). This is the ONLY mechanism by which one worker's findings reach
    a later worker; there is no direct channel (§D.9.1)."""
    task_id: str
    plan_version: int
    covers_waves: list[int]                       # waves whose WCPs are summarized here
    for_wave: int
    interfaces_changed: list[dict]                # [{symbol_id, before, after, by_subtask}]
    files_touched: list[str]                      # merged + deduped across covered waves
    discovered_dependencies: list[str]            # symbol_ids / paths
    constraints_for_next_waves: list[str]         # short strings; long detail → artifact_refs
    unresolved_issues: list[str]                  # ClarificationEscalation ids still open
    artifact_refs: list[str]                      # Blackboard pointers
    token_budget: int                             # hard cap (§B.5's table, "wave → wave" row)
    truncated: bool                               # True → items dropped; drop order in §D.10.6

class ImplementationResult(TypedDict):
    """One entry per CodeGen branch outcome. Appended to SDLCState.implementation_results
    (append_only). Merge uses merge_eligible (§D.4.1); blocked/failed never merge."""
    subtask_id: str
    worker_id: str
    attempt_number: int
    plan_version: int                 # which ExecutionPlan generation dispatched this
    wave_index: int                   # which wave within that plan
    diff_ref: str                     # Blackboard pointer — not inlined
    touches_files: list[str]          # cross-checked against WCP.touches_files at fan-in
    status: Literal["validated", "blocked", "failed"]
    # validated: passed Validator(implementation) at write time — merge-eligible ONLY if
    #            (subtask_id, plan_version, attempt_number) ∉ demotion_ignore_keys (§D.4.1 merge_eligible)
    # blocked:   worker stopped via ClarificationEscalation — never merged
    # failed:    validation exhausted or unrecoverable error — never merged
    # Rows are append-only and NEVER rewritten. Demotion does not change this status;
    # it adds the attempt key to SDLCState.demotion_ignore_keys.

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
    """Mandatory, structured self-report EVERY dispatched worker emits on branch exit —
    success or stop — in EVERY topology (§D.10). Produced as part of the SAME model call
    that produces the worker's primary output wherever possible (structured-output schema,
    §E.3), not a second LLM round-trip.

    Two distinct consumers, which is why this survives the move away from parallel-only:
      1. Fan-in Coordinator (§D.4.1) — detects cross-worker assumption drift and interface
         conflicts within a wave. Vacuous when wave width == 1.
      2. WaveHandoffNote assembly (§D.10.6) — carries wave K's discoveries to wave K+1.
         This consumer is MORE load-bearing under sequential/hybrid execution, not less:
         it is the only sanctioned path by which one worker's findings reach another."""
    subtask_id: str
    worker_id: str
    plan_version: int                             # ExecutionPlan generation that dispatched it
    wave_index: int                               # wave within that plan
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
    previous_plan: ExecutionPlan                   # so the Manager sees the schedule it is revising
    previous_topology_decision: TopologyDecisionRecord
    completed_wave_indices: list[int]              # already merged — NOT to be re-planned (§D.10.5)
    previous_assumptions: list[str]                # aggregated from prior WCPs
    validator_findings: list[dict]                 # prior FeedbackReport.validator_findings
    wcp_summaries: list[str]
    unresolved_clarifications: list[ClarificationEscalation]
    prior_manager_decisions: list[str]
    affected_worker_ids: list[str]
    repo_discoveries: list[str]                    # net-new facts surfaced since original decomposition
    discovered_edges: list[SubtaskDependencyEdge]  # runtime edges that triggered this replan
    unresolved_risks: list[str]

class ContextLedgerEntry(TypedDict):
    """One durable, structured fact about this task, with provenance. The Context Ledger
    (§H.5) is the mechanism that makes 'critical information survives compression' a
    guarantee rather than a hope: ledger entries are DERIVED deterministically from typed
    state, are small by construction (short statement + pointer), and are NEVER an input to
    the compression pipeline — they sit in the pinned context tier (§H.6, Tier 0)."""
    fact_id: str
    task_id: str
    kind: Literal["decision", "constraint", "interface", "assumption",
                  "discovered_fact", "unresolved_issue", "error", "validation_result"]
    subject: str                                   # symbol_id, file path, module, or subtask_id
    statement: str                                 # ≤ 200 chars; detail lives behind provenance_refs
    provenance_refs: list[str]                     # Blackboard pointers / WCP ids / escalation ids
    phase: str
    plan_version: int | None
    wave_index: int | None
    confidence: float
    status: Literal["active", "superseded", "resolved"]
    created_at: datetime

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

    # ── Execution topology (Development phase only, §D.10) ────────────
    # `execution_plan` is REPLACE-semantics (single current plan); every superseded plan
    # is preserved in `topology_decisions`, so replacing it loses no audit history.
    execution_plan: ExecutionPlan | None
    plan_version: int                                          # mirrors execution_plan.plan_version
    current_wave_index: int                                    # -1 before first dispatch
    topology_decisions: Annotated[list[TopologyDecisionRecord], append_only]
    wave_handoff_notes: Annotated[list[WaveHandoffNote], append_only]
    plan_amendment_count: int                                  # bounded by §D.10.5's cap
    demotion_ignore_keys: list[dict]                           # replace-semantics; [{subtask_id, plan_version, attempt_number}]
                                                               # Fan-in merge eligibility must skip these keys (§D.4.4)
    
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

    # ── Context management (§H.5) ─────────────────────────────────────
    # Structured durable facts, never compressed. Small by construction; if this list
    # grows past its cap, superseded/resolved entries are evicted first (§H.5).
    context_ledger: Annotated[list[ContextLedgerEntry], append_only]
    compaction_events: Annotated[list[dict], append_only]      # {trigger, before_tokens, after_tokens, scope}
    
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

**Not the same knob as TP-02:** topology width uses a separate safety threshold `confidence_score is None OR < 0.70` (§D.10.3 TP-02 / `tp02_confidence_floor`). Implementation floor **0.75** escalates model tier / Feedback Agent. Do not unify these numbers.




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
| **wave → wave** (`WaveHandoffNote`, §D.10.6) | **2,000**     |
| Implementation → QA                    | 2,000                |
| QA → Deployment                        | 1,000                |
| Any → HITL                             | 3,000                |

The **wave → wave** row is the hard cap for `WaveHandoffNote.token_budget`. It is an *intra-phase* handoff assembled by Fan-in (deterministic), not a phase Manager packet — but it uses the same size-budget discipline as `PhaseHandoffPacket`.




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
| **Event** (span event) | Instant facts that are not themselves timed work: WCP emitted, clarification raised, feedback-loop fired, kill-switch tripped, wave_demotion | Cheap; does not invent fake durations. |
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
      └── TOPOLOGY_SELECTION             # plan_execution_waves; attributes: topology_class, policy_rules_fired, widths
      └── WAVE_SCHEDULER                 # one span per wave dispatch; attributes: wave_index, width, plan_version
           └── AGENT × width             # Send branches
      └── FAN_IN                          # per wave; events: overlap_detected, wave_demotion, plan_amended, wave_handoff_assembled
      └── HITL                            # interrupt wait; duration = wall clock until resume
```

`Send` branches are sibling AGENT spans under the current WAVE_SCHEDULER (or MANAGER if no scheduler span yet in older traces). Fan-in is a sibling of that wave's agents, not a child of one worker.

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
    "topology_selection", "wave_scheduler",
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

Fan-in Coordinator (Phase 06) records a FAN_IN span plus events: `overlap_detected`, `semantic_conflict`, `wave_demotion`, `plan_amendment`, `replan_triggered` — attributes are booleans/counts/subtask_ids, not diffs.

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
| **3 — Minimal Repo Intelligence**      | Working retrieval at small scale before scaling              | Tree-sitter symbol index; Zoekt trigram search; working-tree content-hash incremental indexing; pgvector store                                          | Phases 0, 2      | Retrieval precision@5 ≥ 90% on held-out labeled set; incremental update < 10s for a 20-file working-tree change               |
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
│   ├── Implementation Manager (ONE structured LLM → TaskDecomposition; then Python selector)
│   ├── Topology Selector (deterministic, no model call, §D.10.3)
│   │     → ExecutionPlan (waves) + TopologyDecisionRecord
│   ├── Wave Scheduler ◀──────────────────────┐  (deterministic loop node, §D.4.0)
│   │     ├── [Send API → CodeGen × width,    │   isolated worktrees (§D.4.3)]
│   │     │     each branch: CodeGen → Validator(implementation) [per-branch, tool-only]
│   │     └── Fan-in Coordinator (deterministic, per wave, §D.4.1)
│   │              ├── merge → WaveHandoffNote → next wave ──┘
│   │              ├── conflict → wave demotion (§D.4.4)
│   │              ├── new dependency → plan amendment (deterministic, §D.10.5)
│   │              └── broken decomposition → bounded Manager replan (§D.9.6)
│   └── Integration Validator (§E.8 — runs ONCE after the final wave, on the full merged set)
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




## D.4 Wave Execution & Conflict Handling

Fan-out via `Send` API for: implementation sub-tasks within a wave, parallel QA tool runners, embedding generation.

> **Scope of Revision 3.1:** §D.4 describes the **Development (Implementation) phase's wave executor**. QA's parallel tool runners and embedding fan-out are unchanged — they are genuinely independent tool invocations with no inter-task dependency structure, so a topology decision would have nothing to decide.

### D.4.0 Canonical Implementation Subgraph Order

Every document describing the implementation phase MUST use this exact sequence. There is **one** executor; parallel, sequential, and hybrid are all expressed as different `ExecutionPlan.waves` shapes (§D.10.1) — not different code paths.

```
Implementation Manager (LLM)
  → TaskDecomposition (WHAT: sub-tasks, scopes, declared dependencies)

Topology Selector (deterministic, zero LLM calls, §D.10.3)
  → SubtaskDependencyGraph (RI-verified typed edges)
  → ExecutionPlan (WHEN: ordered waves) + TopologyDecisionRecord (WHY)

Wave Scheduler (deterministic loop node) — for wave_index = 0 … N-1:
  │
  ├─ Send fan-out: one branch per subtask_id in waves[wave_index]
  │     (dispatched ≤ dispatch_concurrency at a time; width==1 ⇒ an ordinary
  │      single-branch dispatch, NOT a special "sequential mode")
  │
  │   Per branch (isolated worktree, §D.4.3):
  │     1. CodeGen Sub-agent → diff + WorkerCoordinationPacket (Blackboard refs)
  │        (context = sub-task spec + WaveHandoffNote for this wave, §D.10.6)
  │     2. Validator(implementation) [static-analysis, tool-only, independent of CodeGen]
  │          ├─ pass → append ImplementationResult(status="validated")
  │          └─ fail → FL-04 → FeedbackReport → retry CodeGen (same subtask_id, attempt_number++)
  │                    └─ 3× fail on same module → Feedback Agent → HITL if still failing
  │
  ├─ Fan-in Coordinator (§D.4.1) — runs at the end of EVERY wave, in every topology
  │     ├─ merge merge_eligible branches into the integration worktree
  │     ├─ assemble WaveHandoffNote for the next wave (§D.10.6)
  │     ├─ conflict → wave demotion SM (§D.4.4)
  │     ├─ new blocking edge affecting only undispatched waves → plan amendment (§D.10.5)
  │     └─ needs_manager_attention / open escalation → bounded Manager replan (§D.9.6)
  │
  └─ more waves remain? ──yes──▶ loop to next wave
                          └no──▶ exit loop

Integration Validator (ONCE, after the final wave, on the full merged diff set)
  └─ fail → FL-05 → Implementation Manager (re-assign, max 2×)
```

**Key invariants:**

1. `Validator(implementation)` runs **per branch, before Fan-in** — never on the merged result. Merge uses `merge_eligible` (§D.4.1). `FL-04` targets the originating CodeGen sub-agent because validation is per-diff, not post-merge.
2. **Fan-in runs per wave; Integration Validator runs once per implementation attempt.** Fan-in is deterministic and near-free, so running it after every wave costs almost nothing and is what makes cross-wave conflict detection possible. Integration Validator is a High-capability agent with sandboxed test execution — running it per wave would multiply the phase's cost by the wave count for no correctness gain.
3. **A width-1 wave is not a special case.** Fan-in still runs. Its intra-wave comparisons (decisions 2, 3, 5) are trivially empty, but its cross-wave check, its merge authority, and its handoff-note assembly all still apply. Preserving one code path across all topologies is the entire point of §D.10.1.

**Responsibility ownership (no duplicates):**

| Responsibility | Owner | Must not |
|---|---|---|
| WHAT (subtasks, scopes, declared deps) | Implementation Manager (LLM) | Topology, waves, width, Send |
| DAG correctness (blocking edges) | SDG / RI in Topology Selector | Delete blocking edges for throughput |
| Conservatism (max_wave_width) | TP-01…TP-08 YAML + profile/ctx bounds | Invent edges or subtasks |
| WHEN / how much (waves, dispatch) | `plan_execution_waves` + Wave Scheduler | LLM |
| Mechanical `Send` | **Wave Scheduler only** | Manager, Fan-in, workers |
| Independent execution | CodeGen workers | Sibling comms, merge |
| Wave boundary / merge / demote / amend / handoff | Fan-in (deterministic) | LLM, unmerge completed waves |
| Per-branch static check | Validator(implementation) | Judge merged contracts |
| Merged-contract judgment | Integration Validator (once) | Run per wave |
| Historical attempts | append-only results/WCP + `demotion_ignore_keys` | Rewrite rows |

### D.4.0.1 Representing the wave loop in LangGraph

The wave loop is a **scheduler node that re-enters itself**, not a set of statically declared per-wave nodes. LangGraph graphs are compiled ahead of time; the number of waves is known only at runtime.

| Concern | Mechanism |
|---|---|
| Dynamic fan-out of unknown width | `Send(codegen_branch, subtask_payload)` returned from the scheduler's conditional edge — one `Send` per subtask in the current wave |
| Advancing to the next wave | Fan-in returns `Command(goto="wave_scheduler")` after incrementing `current_wave_index` |
| Termination | Scheduler routes to `integration_validator` when `current_wave_index >= len(execution_plan.waves)` |
| Parallel-safe state merge | All per-branch writes land in `append_only` channels (`implementation_results`, `worker_coordination_packets`, `clarification_escalations`). No branch writes a replace-semantics field — this is what prevents concurrent-update errors at superstep boundaries |
| Loop bounding | `recursion_limit` must be set to at least `waves × (retries+1) × 3`; independently, `plan_amendment_count` and the replan cap bound the number of loop re-entries (§D.10.5). Exceeding either is a Fail-Closed escalation, never a silent stop |
| Checkpoint size | `ExecutionPlan` is replace-semantics and small (ids + edges, no payloads). Diffs and logs remain Blackboard pointers (§D.9.4) |
| Wave-close compaction | `compact_at_wave_close` is invoked from Fan-in after handoff. **Phase 06: no-op stub.** Phase 12 implements T2/T3. Topology must not depend on compaction succeeding. |

**Why a scheduler loop rather than compiling one node per wave:** the wave count depends on a dependency graph that is only known after the Manager decomposes, and it changes at runtime under amendment (§D.10.5). A statically compiled per-wave topology would have to be recompiled mid-task, which discards the checkpointer's graph identity and makes resume-after-crash unreliable. One self-re-entering node is stable across recompiles, checkpoints cleanly, and is the idiom LangGraph's `Send` + `Command(goto=...)` pair is designed for.

### D.4.1 Fan-in Coordinator (deterministic, not an agent)

Every wave's fan-out (`Send`) is closed by a **Fan-in Coordinator** graph node. This is explicitly **not an LLM call, not an agent, and not a reasoning component** — it is a deterministic function over branch outputs and their `WorkerCoordinationPacket`s (§D.9.2). Its job is to decide, by rule, what happens next; it never generates or resolves code itself.

**Input scope:** Fan-in runs only after every branch **in the current wave** is **terminal**: `ImplementationResult.status` ∈ {`validated`, `blocked`, `failed`}. Branches mid-FL-04 retry do not trigger fan-in — LangGraph keeps the branch open until validation passes or exhausts.

**Single merge-eligibility predicate (`merge_eligible`, source of truth):**

```
merge_eligible(r: ImplementationResult) iff
    r.status == "validated"
    AND (r.subtask_id, r.plan_version, r.attempt_number) not in demotion_ignore_keys
```

ImplementationResult rows are never rewritten. Demotion only adds keys to `demotion_ignore_keys`.

**Decisions the Fan-in Coordinator performs, in order:**

1. **WCP / result selection** — for each `subtask_id` in this wave, take the packet/result with the highest `(plan_version, attempt_number)` that is `merge_eligible`. Blocked/failed terminals are visible for replan (decision 8) but never merged.
2. **Intra-wave overlap detection** — file sets touched by each merge-candidate branch in this wave (`WorkerCoordinationPacket.touches_files`, cross-checked against `ImplementationResult.touches_files` and the Blackboard diff). Flags pairwise overlap. *No-op when wave width is 1.*
3. **Intra-wave semantic conflict detection (WCP-based, deterministic)** — §D.4.1.1. *No-op when wave width is 1.*
4. **Cross-wave compatibility check** — for each merge-candidate in this wave, compare its `touches_files` and consumed symbols against **prior** `WaveHandoffNote` history (waves `0..current-1` already merged). Detects: editing a file an earlier wave already changed in a conflicting way; assuming a signature that an earlier wave changed incompatibly. Runs at every wave width, including 1. Uses §D.4.1.1 rules with the accumulated handoff note substituted for sibling WCPs. If the conflict is against **already-merged** work that cannot be demoted, escalate to Manager replan (§D.4.4.4) — do not unmerge.
5. **Merge eligibility** — remaining `merge_eligible` candidates with no flagged overlap/conflict are merged into the integration worktree (§D.4.3).
6. **Wave demotion** — if conflict set `C` has size ≥ 2 among this wave's candidates, run §D.4.4 state machine (supersede all of `C`, amend active plan, redispatch). Never silently auto-merge.
7. **Plan amendment (pure)** — any `discovered` dependency in this wave's WCPs that constrains only **not-yet-dispatched** subtasks (and did not already enter demotion) is added to the SDG; remaining waves re-levelized. Bounded by `plan_amendment_count` (§D.10.5).
8. **Replanning trigger** — `needs_manager_attention`, open `ClarificationEscalation`s, demotion abort (cycle), or cross-wave-vs-merged escalation → at most one Manager replan per wave per attempt (§D.9.6).
9. **`WaveHandoffNote` assembly** — union/dedup/priority-truncate over **merge-eligible** WCPs only (§D.10.6). Zero model calls.
10. **Advance or exit** — if unexecuted waves remain in the **active** plan, increment `current_wave_index` and `Command(goto="wave_scheduler")`. Else → Integration Validator.

**Topology-independence of this node is a deliberate design property.** Under a single wide wave (parallel) decisions 2/3 do the work; under N width-1 waves (sequential) decisions 4/9 do the work; under a hybrid DAG all of them do. There is no branch in this node on `topology_class` — it reads `ExecutionPlan.waves` and behaves accordingly.

#### D.4.1.1 WCP Semantic-Conflict Matching Rules (v1, deterministic, no LLM)

For each unordered pair of branches `(A, B)` where both have `status="validated"`:

1. **Symbol normalization:** every `interface_changes[].symbol` and every token extracted from `assumptions`/`discovered_dependencies` is normalized to RI `symbol_id` format: `{file_path}::{qualified_name}` (§G.6.1). Strip whitespace; lowercase file paths; leave qualified names case-sensitive.
2. **Direct symbol match:** conflict if any `A.interface_changes[].symbol` equals any entry in `B.assumptions` or `B.discovered_dependencies` after normalization, OR vice versa.
3. **Substring fallback (assumptions only):** if step 2 finds no match, conflict if any normalized `A.interface_changes[].symbol` appears as a substring in any normalized `B.assumptions` string (or vice versa). Do **not** apply substring matching to `discovered_dependencies` — exact symbol_id match only for that field.
4. **RI caller cross-check:** for each `interface_changes[].symbol` in branch A, call `get_callers(symbol, depth=1)`. Conflict if any caller's `symbol_id` appears in branch B's `assumptions` or `discovered_dependencies` (normalized exact match).
5. **Parse failure → Fail-Closed:** if any WCP field required for steps 1–4 is missing or fails schema validation, set `needs_manager_attention=true` on that WCP and route to Manager replan (step 6 above) — never silently treat as non-conflicting.
6. **RI unavailable during cross-check:** if step 4's RI call fails or times out, treat as conflict (Fail-Closed) and enter **wave demotion** if `|C|≥2`, else Manager replan — never assume no conflict.

Overlapping/conflicting branches are **never** silently merged — this correctness-over-throughput stance is unchanged from earlier revisions of this document, now made precise by having the Coordinator's exact decision list written down instead of left to "the fan-in node checks for overlaps."

**File-level overlap detection is the v1 granularity, by design** — it is the simplest mechanism that is never *wrong in the unsafe direction* (it may over-trigger a re-run on two agents editing unrelated parts of the same large file, but it will never miss a real conflict the way naive line-level diffing could). Finer-grained detection is future roadmap only, not v1:

- **Symbol-level overlap** (two branches touch different functions in the same file — currently treated as a conflict at file granularity) — revisit once real conflict-rate data (Phase 15's loop-trigger-rate KPI) shows file-level granularity is a genuine throughput problem, not before.
- **AST-level / semantic dependency-graph overlap detection** (beyond the WCP-based interface-change check in decision 2 above) — a research-track item, not scheduled into any v1 phase.
- **Any LLM-assisted "predict likely conflicts before dispatch" mechanism** — evaluated and deferred; the deterministic post-hoc check above is cheaper and more auditable than a predictive model that could be wrong in either direction.

At high task volume, concurrent graphs hit shared Repository Intelligence stores. Mitigation: read/write separation (incremental-indexing writes → primary; agent-execution reads → replicas).

### D.4.2 Pre-dispatch Overlap Check → superseded by Topology Selection

> **Changed in Revision 3.1.** V3.0's "pre-dispatch overlap check" was an *optional* deterministic scan the Manager ran immediately before `Send()`. It has been **promoted into a mandatory, first-class component**: the Topology Selector (§D.10.3), which performs the same file/symbol/dependency comparison and then goes further — it builds a typed dependency graph and derives the entire wave schedule from it. The old check is not deleted; it is subsumed. Do not implement both.

What the Topology Selector does with the inputs V3.0 listed:

| V3.0 pre-dispatch input | V3.1 use |
|---|---|
| `ownership_map` — which sub-task claims which scope | Source of `file_overlap` / `symbol_overlap` edges (§D.10.2) |
| Planned file sets per sub-task (decomposition + RI file index) | Same; plus `shared_resource` edge derivation from the L4 architecture summary |
| Dependency graph consistency (`get_dependencies`/`get_dependents`) | Source of `produces_interface` edges, and verification of the Manager's `declared` edges |
| "Merge overlapping sub-tasks or move one to a later group" | Now a rule with a defined precedence: overlap on the *same file with no ordering that resolves it* → merge sub-tasks; overlap that a strict ordering resolves → separate waves (§D.10.3 step 3) |

**Unchanged:** this remains an optimization in the safety sense — the Fan-in Coordinator (§D.4.1) is still the **final authority**. Workers may touch files outside their assigned scope during execution, and only Fan-in sees what actually happened. Pre-dispatch analysis reduces avoidable re-run cycles; it never licenses skipping a Fan-in check.

### D.4.3 Git Isolation Contract

Minimal, binding rules for parallel CodeGen and Fan-in merge. No new agents — enforced by sandbox + worktree permissions.

| Concept | Convention |
|---|---|
| **Base commit** | `task_base_sha` — repo HEAD at Implementation Manager dispatch time; immutable for the task attempt. **Wave 0 branches only.** |
| **Base commit, waves ≥ 1** | **Integration HEAD** as of the previous wave's Fan-in merge. This is what makes sequential and hybrid execution meaningful at the git level: a later wave's worker sees earlier waves' applied changes in its working tree, not just in its handoff note. A wave-0 branch and a wave-3 branch therefore have different bases *by design* |
| **Wave base (demotion)** | When a subtask is redispatched after demotion, its worktree is created from **integration HEAD at redispatch time** (after any non-conflicting siblings from the failed wave have merged, and after any ordered predecessors in the demotion serial chain have merged). Never reuse a discarded conflict worktree in place. |
| **Per-branch worktree** | `{repo_root}/.sdlc/worktrees/{task_id}/{subtask_id}/` on branch `sdlc/{task_id}/{subtask_id}` (one per `(task_id, subtask_id)` at a time — a demoted sub-task's worktree is destroyed and recreated from the new base) |
| **Integration worktree** | `{repo_root}/.sdlc/worktrees/{task_id}/integration/` on branch `sdlc/{task_id}/integration` |
| **Branch naming** | `sdlc/{task_id}/{subtask_id}` for workers; `sdlc/{task_id}/integration` for merged result |
| **Allowed writers** | CodeGen sub-agent → its own per-branch worktree only. Fan-in Coordinator → integration worktree only. No other component writes git state during implementation. |
| **Merge authority** | Only Fan-in Coordinator applies `merge_eligible` branch diffs into the integration worktree. Workers never merge. |
| **Cleanup** | Remove all `{task_id}` worktrees/branches on: successful Implementation phase exit, task cancellation (§D.9.9), or task completion. Partial cleanup on fan-in merge success is allowed but full task cleanup is mandatory at phase exit. |

**Blackboard pointer format (all services):** `{task_id}/{kind}/{uuid}` — e.g. `abc123/diff/7f3a…`. Returned by `BlackboardService.store()`; accepted by `retrieve()` and `exists()`.

### D.4.4 Wave Demotion — Formal State Machine

**Wave demotion** is the deterministic recovery path when Fan-in decision 6 fires (intra-wave file overlap, intra-wave semantic conflict, or cross-wave incompatibility involving branches that just finished). It replaces V3.0's ad-hoc "serialize-and-rerun" node.

#### D.4.4.0 Active plan vs historical record (mandatory distinction)

| Concept | Storage | Mutable after demotion? |
|---|---|---|
| **Active `ExecutionPlan`** | `SDLCState.execution_plan` (replace-semantics) | **Yes** — remaining schedule is rewritten (`plan_version++`, `created_from="amendment"`) |
| **Historical topology decisions** | `SDLCState.topology_decisions` (`append_only`) | **No** — prior `TopologyDecisionRecord` rows remain |
| **Historical attempts** | `implementation_results`, `worker_coordination_packets` (`append_only`) | **No** — old rows stay; conflicting ones are marked non-mergeable |
| **Telemetry** | `TelemetrySink` events (`wave_demotion`, …) | Append-only audit |

**Forbidden representation:** leaving the live plan as `Wave0=[A,B]` plus an extra `Wave1=[B]` while A's conflicting result remains mergeable. That mixes history with the active schedule and allows accidental double-merge.

**Correct mental model:** Wave0 *attempted* `[A,B]` (recorded in telemetry + superseded/ignored results). The *active* plan after demotion places A and B in **later distinct waves** (usually width 1). Neither old result may merge.

#### D.4.4.1 Trigger

Fan-in selected validated results for the current wave and computed a **conflict set** `C` with `|C| ≥ 2`.

#### D.4.4.2 State machine (deterministic, zero LLM)

```
DEMOTION_BEGIN(conflict_set C, current_wave_index W, plan P @ plan_version=v)

S1. FREEZE_MERGE
    No member of C is merge-eligible.
    Non-members S = (validated in wave W) \ C remain eligible and are merged
    under decision 5 before S2 (siblings must not be stranded).

S2. SUPERSEDE
    For each subtask_id in C:
      - add (subtask_id, plan_version, attempt_number) to
        SDLCState.demotion_ignore_keys (replace-semantics set).
        Do NOT rewrite ImplementationResult.status (append-only).
      - destroy worktrees for those subtask_ids (§D.4.3).
    Historical WCPs/results remain; merge_eligible and WaveHandoffNote ignore them.

S3. ORIENT
    Build total order O = [T0, T1, … Tk] over C:
      a. If evidence implies direction (e.g. produces_interface Ti→Tj), add that
         blocking discovered edge.
      b. For every still-undirected conflicting pair, orient lexicographically:
         smaller subtask_id → larger subtask_id (smaller runs first).
      c. Topological sort → O.
      d. If a cycle remains → abort demotion; Fan-in decision 8 (Manager replan)
         with ReplanContext.discovered_edges. HITL if replan also cycles (§D.10.9).

S4. AMEND_ACTIVE_PLAN  (demotion ⊆ plan amendment, §D.10.5)
    - Add all blocking discovered edges from S3 to the SDG.
    - Waves 0..W-1 already fully merged are IMMUTABLE (completed_wave_indices).
    - Remove all members of C from any not-yet-completed active wave entry.
    - Let R = (undispatched subtask_ids ∪ C).
    - Re-run levelize + width-cap (§D.10.3 Steps 4–5) on R only.
      Amendments must not widen max_wave_width; new edges may only deepen/narrow.
    - plan_version = v+1; created_from = "amendment"; superseded_plan_version = v.
    - Append TopologyDecisionRecord; increment plan_amendment_count.
    - If plan_amendment_count > max_plan_amendments (default 3) → Manager replan.

S5. RECORD_HISTORY
    Emit TelemetrySink event "wave_demotion":
      {wave_index: W, conflict_set: C, order: O, old_plan_version: v,
       new_plan_version: v+1, edges_added: [...]}
    Do not keep the conflicting parallel set as an executable active wave.

S6. REDISPATCH
    Command(goto="wave_scheduler") at the first not-yet-executed wave of the
    amended active plan.
    For each redispatched subtask:
      attempt_number += 1
      idempotency key = (task_id, subtask_id, plan_version, attempt_number)
      worktree base = integration HEAD at dispatch time
        (T0 after sibling merges; T1 after T0 merges; …)

S7. CONTINUE
    Fan-in re-runs decisions 1–10 after every subsequent wave.
    Integration Validator runs only after the final active wave completes
    conflict-free (or escalates).
```

#### D.4.4.3 Contract answers

| Question | Contract |
|---|---|
| Winner keeps its diff? | **No.** All of `C` are made non-`merge_eligible` via `demotion_ignore_keys`. “Earlier in `O`” ≠ keep diff. |
| Order? | Directed evidence if present; else lex `subtask_id`; topo-sort (S3). |
| Both discarded and rerun? | **Yes.** |
| Base for T0 / T1..Tk? | Integration HEAD at each dispatch; after predecessor merges for later Ti. |
| Old WCP / ImplementationResult? | History retained; not merge-eligible; handoff ignores superseded attempts. |
| `plan_version` / `attempt_number`? | `plan_version++` once per demotion amendment; `attempt_number++` per redispatched subtask. |
| Active `ExecutionPlan.waves`? | **Rewritten** for remaining work. |
| Completed waves immutable? | **Yes.** |
| Demotion ⊆ amendment? | **Yes.** |
| Termination? | Adds ≥1 blocking edge; ≤ n² edges; amendment cap → replan. |
| A↔B cycle? | S3.d → Manager replan (not demotion). |
| 3+ workers? | Same machine on full set `C` → total order → serial blocking chain. |

#### D.4.4.4 Cross-wave conflict against already-merged work

If decision 4 fails against an **already merged** earlier wave, demotion cannot unmerge that wave (§D.6). Fan-in triggers **Manager replan** (decision 8) / HITL — not S1–S7.

#### D.4.4.5 Example

```
Before: active Wave0 = [A, B]   # believed independent
Both validate → Fan-in file_overlap(A,B); assume "A" < "B"

History: wave_demotion {conflict_set:[A,B], order:[A,B], v→v+1}; attempts superseded
Active plan (v+1): Wave0'=[A], Wave1'=[B] with discovered blocking edge A→B
Git: A from integration HEAD; after A merges, B from new HEAD
```

**Not** active plan `Wave0=[A,B]; Wave1=[B]`.

---

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

Every dispatched worker (CodeGen sub-agents, §E.8; any future `Send`-dispatched worker) emits a `WorkerCoordinationPacket` (schema §B.2) on branch exit — success or stop — in **every** topology.

WCP is **not** “parallel-only glue.” It has two jobs:

1. **Intra-wave evidence** for Fan-in conflict detection (vacuous when width=1).
2. **Raw material** for `WaveHandoffNote` projection to later waves (load-bearing under sequential/hybrid).

| Property | Value |
|---|---|
| **Producer** | The worker, as structured fields of the same model call that produces the diff when possible |
| **Consumers** | Fan-in (§D.4.1); WaveHandoffNote assembly (§D.10.6); Manager replan via `ReplanContext` |
| **Lifecycle** | One WCP per dispatch attempt; append-only; non-mergeable attempts excluded via `demotion_ignore_keys` + `merge_eligible` |
| **Storage** | Small fields inline; diffs/logs via `artifact_refs` → Blackboard |
| **Must include** | `plan_version`, `wave_index` (attribution + idempotency) |
| **Must NOT become** | A free-form chat log, a full diff dump, or a worker↔worker inbox |

**Projection into `WaveHandoffNote` (copied):** interface_changes → interfaces_changed; touches_files; discovered_dependencies; short risks → constraints; open escalation ids; Blackboard refs for truncated items.

**Not copied into next-worker context:** raw diffs, tool traces, full assumption essays, sibling WCPs wholesale, mid-flight state. Next workers get the capped note + progressive RI tools + Context Ledger (T1). This is what keeps 100k+ file repos tractable.

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
Fan-in Coordinator batches all escalations from the wave (D.4.1 decision 8)
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
- **Batched, not streamed** — the Manager resolves a whole wave's escalations in at most one reasoning pass per batch, not one call per escalation.
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

## D.9.5 Coordination Authority vs Mechanical Dispatch (`Send`)

Explicit, project-wide. **Two different privileges must not be conflated:**

| Privilege | Who | What it means |
|---|---|---|
| **Coordination authority** | Phase Manager only (Implementation Manager here) | Decompose work, replan, reassign scope, resolve escalations, authorize that an `ExecutionPlan` may run |
| **Mechanical dispatch** | **Wave Scheduler node only** | Return LangGraph `Send(codegen_branch, …)` for subtasks in the *current active wave* |
| **Neither** | Workers / CodeGen | Never `Send`, never replan, never reassign |

| May do | Manager | Wave Scheduler | Worker |
|---|---|---|---|
| Decompose / replan / reassign | ✅ | ❌ | ❌ |
| Produce / amend `ExecutionPlan` via Topology Selector call sites | ✅ (initial + replan); Fan-in may call amendment path | ❌ (consumes plan only) | ❌ |
| Return `Send` for CodeGen | ❌ | ✅ | ❌ |
| Emit WCP / ClarificationEscalation | ❌ | ❌ | ✅ |

**Why Wave Scheduler issues `Send` (not the Manager node):** LangGraph fan-out must happen from the node whose conditional edge returns `Send` objects at the wave boundary. The Manager is an LLM node that should not also be the fan-out edge. The Scheduler is a **deterministic orchestration node** in the Implementation subgraph — it is not a Worker and not an LLM. This preserves `max_parallelism` enforcement: only the Scheduler can open branches, and only for ids present in `execution_plan.waves[current_wave_index]`.

**Mechanically enforceable checks (acceptance tests):**
1. Grep/graph audit: no CodeGen node returns `Send`.
2. Wave Scheduler refuses to dispatch ids not in the active wave.
3. Workers have no graph edge that can invoke `Send`.

A worker that needs help raises `ClarificationEscalation` and stops; only the Manager redispatches via a new plan consumed by the Scheduler.

### D.9.6 Conditional Coordination (No Always-On Meetings)

Coordination beyond the default isolated-worker → fan-in path happens **only when triggered**, never on a fixed schedule or "just in case":

| Trigger | Resulting coordination |
|---|---|
| A `WorkerCoordinationPacket.needs_manager_attention = true` | Fan-in Coordinator batches it into a bounded Manager replan |
| One or more `ClarificationEscalation`s in a wave | Same batched Manager pass (§D.9.3) |
| Neither of the above | **No coordination step runs at all** — straight to merge/Integration Validator |

**Bound:** at most **one** Manager coordination/replan pass per **wave** per attempt. If that pass's redispatch still fails validation, the task proceeds through the normal `FL-04`/`FL-05`/Feedback Agent escalation chain (§D.5, §D.8) rather than triggering a second ad-hoc coordination round.

### D.9.7 Communication Non-Goals (Reject on Sight)

The following are explicitly out of scope for this architecture. Naming them here is deliberate — to prevent future architectural drift toward "just this once" exceptions:

- **Worker ↔ worker communication of any kind**, direct or relayed through a shared mutable object they both poll.
- **Swarm or emergent multi-agent coordination** for any core SDLC workflow (see the platform's own decentralized-patterns evaluation — swarm/peer-to-peer/voting/auction/full consensus were assessed and rejected for the control plane).
- **Debate architectures as a default mechanism.** (Bounded, opt-in design-debate for Critical/High-risk design exploration remains a *separate*, policy-gated research track — it is not part of this communication protocol and does not relax the worker-isolation invariant.)
- **Always-on coordination meetings/windows** that run unconditionally on every task (§D.9.6).
- **Recursive worker spawning** — only the Wave Scheduler may `Send`; only Managers hold coordination authority (§D.9.5).
- **An LLM-driven Merge Resolution Agent** that creatively resolves conflicting diffs. Merge conflicts are handled by Fan-in **wave demotion** (§D.4.4), never by asking a model to reconcile two diffs into one. This is a correctness and auditability decision, not an oversight: an auto-merged "creative" resolution is exactly the kind of silent, unverifiable change Principle 5 (deterministic/auditable over clever) exists to prevent.
- **Using `messages` (§B.2) as an inter-agent bus.** It is the human/system conversation transcript only (§B.2's field comment) — agent coordination has its own typed channels (`worker_coordination_packets`, `clarification_escalations`, `feedback_reports`).

### D.9.8 Worker Lifecycle

```
Created (Send dispatch from Wave Scheduler)
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



## D.10 Dynamic Execution Topology (Development Phase)

This section specifies the complete architecture for runtime topology selection in the Development phase. Everything in §D.4 is the wave executor; this section is the layer that decides the wave schedule.

### D.10.1 One executor, not three code paths

**PARALLEL, SEQUENTIAL, and HYBRID are not modes — they are shapes of the same `ExecutionPlan`.**

- PARALLEL = no blocking edges in the SDG (independent set; may still be split into multiple waves by width cap only) — see §D.10.3 `topology_class` rules
- SEQUENTIAL = every active wave has `width == 1`
- HYBRID = blocking edges exist **and** more than one wave with mixed structure

`topology_class` is a *derived label* for telemetry/evaluation only. It never switches code paths. The wave executor (§D.4.0) handles all three identically.

#### D.10.1.1 OLD → NEW Development execution (normative)

**OLD (V3.0):**
```
Manager → TaskDecomposition (WHAT only; no schedule field)
       → Send
       → workers → Validator
       → Fan-in (per parallel group)
       → Integration Validator
```

**NEW (Rev 3.1):**
```
Manager → TaskDecomposition (WHAT + declared_dependencies)
       → Topology Selector / plan_execution_waves (WHEN)
       → ExecutionPlan + TopologyDecisionRecord
       → Wave Scheduler (sole mechanical Send per wave)
       → workers → Validator
       → Fan-in per wave (merge / demotion / amendment / WaveHandoffNote)
       → next wave …
       → Integration Validator (once)
```

| | Removed / deprecated | Unchanged | Introduced |
|---|---|---|---|
| Schedule | `TaskDecomposition.execution_order` (removed) | Manager decomposition, WCP, isolation, Blackboard, worktrees, per-branch Validator | SDG, Topology Selector, ExecutionPlan, Wave Scheduler, per-wave Fan-in, WaveHandoffNote, demotion SM, plan amendment |
| Runtime | Three mental “modes” | LangGraph Pregel / `Send` / checkpoints | Topology layer *above* LangGraph (plan is data; compiled graph stays static) |

**Why above LangGraph:** BSP + `Send` + checkpoints remain correct primitives. LangGraph edges are not dependency constraints. The SDG lives in state; the Scheduler loop is the minimal adapter.

---

### D.10.2 Features that drive the topology decision

Features are categorised by measurement reliability.

**Tier A — Static, cheap, pre-dispatch (available before any worker runs):**

| Feature | Source | How it influences topology |
|---|---|---|
| Sub-task declared dependency count / density | `TaskDecomposition.tasks[].declared_dependencies` | High density → narrower waves |
| File-set pairwise overlap across sub-tasks | RI `get_file_structure` + `ownership_map` | Any overlap forces serial ordering of overlapping pair |
| Symbol-set overlap (interface consumers / producers) | RI `get_callers` / `get_callees` (depth 1) | Produces `produces_interface` edges |
| Shared resource detection | Architecture summary L0: DB entities, APIs, config, protos | Produces `shared_resource` edges |
| Sub-task count | `len(TaskDecomposition.tasks)` | Very high count → aggressive width cap |
| Repo-map overlap coefficient | Personalized PageRank map overlap between sub-task seed sets | High coefficient → increase serial ordering |
| DAG topological height | Computed from declared + RI-verified edges | Height > threshold → sequential or narrow hybrid |
| `WorkflowProfile.max_parallelism` | §F.2 | Hard upper bound on wave width |
| Risk tier | `Task.risk_tier` | CRITICAL → hard gate width 1 (TP-03); HIGH → soft cap 2 (TP-05) |
| Change size estimate | `RI.get_impact_set()` over declared target files | Large blast radius → prefer serial |

**Tier B — Runtime-discovered (available mid-execution, triggers plan amendment):**

| Feature | Source | Effect |
|---|---|---|
| WCP `discovered_dependencies` | Worker output on branch exit | New `discovered` blocking edge → plan amendment |
| WCP `interface_changes` conflicting with peer assumptions | Fan-in semantic conflict check | May trigger wave demotion |
| `ClarificationEscalation` revealing scope overlap | Worker stop + escalation | May trigger Manager replan of undispatched sub-tasks |

**Tier C — Historical / learned (Phase 15+, optional):**

| Feature | Source | Future use |
|---|---|---|
| Per-module failure frequency | `regression_history` | Down-weight parallelism for high-failure modules |
| Past conflict rate for similar task-type | `TopologyDecisionRecord` history | Calibrate default width cap |
| Past re-plan rate | `feedback_loop_events` | Increase serial preference for task patterns with high replan rate |

**Tier A features drive the MVP implementation.** Tier B is the plan amendment path. Tier C is experimental, gated on Phase 15 data volume, and governed by `resolve_workflow_profile()` rule updates (§F.3), not embedded in the topology selector itself.

### D.10.3 `plan_execution_waves()` — the deterministic scheduler

`plan_execution_waves()` is a pure function in `packages/orchestration/topology_selector.py`.

**Signature:**
```text
plan_execution_waves(
  decomposition: TaskDecomposition,
  sdg: SubtaskDependencyGraph,          # may be built inside; RI adapter injected
  profile: WorkflowProfile,             # §F.1 — includes max_parallelism
  ctx: WorkflowContext,                 # §F.2 — includes repo_scale, max_parallel_impl_agents
  task: Task,                           # risk_tier, confidence_score (§B.1 / §B.4)
) -> tuple[ExecutionPlan, TopologyDecisionRecord]
```

**No LLM call.** The Manager decides *what*; this function decides *when*.

#### Inputs — exact sources (no guessing)

| Input | Source | Available at planning time? | Notes |
|---|---|---|---|
| `declared_dependencies` | `TaskDecomposition.tasks[]` | Yes | Manager output |
| File/symbol/shared-resource facts | RI queries (§D.10.7 budget) | Yes if `ri_available` | Else hard gate TP-01 |
| `task.risk_tier` | `Task.risk_tier` | Yes | Intake / policy |
| `task.confidence_score` | `Task.confidence_score` from Confidence Model (§B.4), as of Design→Implementation handoff | Yes | If scorer failed → `None` or value `< 0.70` → TP-02 width=1. Distinct from §B.4 Implementation floor **0.75** (model-tier escalate). |
| `ctx.repo_scale` | `WorkflowContext.repo_scale` (§F.2): `small(<1k)` \| `medium(<10k)` \| `large(<100k)` \| `enterprise(100k+)` | Yes | Until Phase 10: derive from RI file-count heuristic in `build_workflow_context` subset; default `medium` if unknown (do **not** default to `small`) |
| `profile.max_parallelism` | `WorkflowProfile.max_parallelism` | Yes | Until Phase 10: `most_conservative()` → `2` |
| `ctx.max_parallel_impl_agents` | computed from `repo_scale` (§F.2) | Yes | enterprise 8 / large 5 / medium 3 / small 2 |

**Removed:** `manager_suggestion` — undefined and redundant. The Manager influences schedule only via declared dependencies and decomposition shape, not via an opaque width hint.

#### Algorithm

```
plan_execution_waves(...):

  Step 1 — Seed SDG from Manager declared edges (kind="declared", blocking=True)

  Step 2 — RI-verify / augment (budget §D.10.7)
     Confirm or refute declared edges; add file_overlap / symbol_overlap /
     produces_interface / shared_resource edges found by RI.
     Cycle detect → Fail-Closed: no plan dispatched; Manager replan (§D.10.9).
     Set sdg.ri_available appropriately.

  Step 3 — Compute max_wave_width via TP policy (below)

  Step 4 — Levelize (correctness)
     Level 0 = nodes with no blocking predecessors among remaining nodes
     Level k = nodes whose latest blocking predecessor is in level k-1
     Within level: HLF order (upward rank = critical-path length)

  Step 5 — Apply width cap (scheduling only)
     Split any level with size > max_wave_width into consecutive waves,
     preserving HLF order. Splits do NOT invent blocking edges.

  Step 6 — Derive topology_class (label only) — see exact rules below
     Build ExecutionPlan + TopologyDecisionRecord
```

#### TP-01 → TP-08 — implementation-ready policy

**Design:** two phases. Hard gates are exclusive (first match → `max_wave_width = 1`, stop). Soft caps all apply via `min` (never widen).

```
profile_bound = min(profile.max_parallelism, ctx.max_parallel_impl_agents)

# ── HARD GATES (ordered, first-match-wins, exclusive) ───────────────
# Each forces fully sequential scheduling when independence cannot be trusted.

TP-01  RI unavailable
       condition: sdg.ri_available == False
       action:    max_wave_width = 1
       prevents:  parallelizing without verifying file/symbol independence
       if info N/A: this *is* the N/A case

TP-02  Low / missing confidence
       condition: task.confidence_score is None OR task.confidence_score < 0.70
       action:    max_wave_width = 1
       prevents:  wide fan-out when requirements/design confidence is weak
       source:    §B.4 Fail-Closed — missing score is never imputed as high
       NOTE:      0.70 is the *topology width* gate (YAML). Distinct from
                  Implementation phase confidence floor 0.75 which escalates
                  *model tier* (§B.4 / §F.3). Do not merge these knobs.

TP-03  Critical risk
       condition: task.risk_tier == CRITICAL
       action:    max_wave_width = 1
       prevents:  concurrent edits on irreversible / highest-blast-radius work
       NOTE:      Resolves prior contradiction: CRITICAL is width 1, not 2.

TP-04  Small repository
       condition: ctx.repo_scale == "small"
       action:    max_wave_width = 1
       prevents:  coordination overhead dominating tiny codebases
       if unknown: do not fire (default repo_scale="medium")

# If any hard gate fired → skip soft caps; final-width formula still records profile/ctx.

# ── SOFT CAPS (all matching contribute; take min with profile_bound) ─
candidates = [profile_bound]

TP-05  High risk
       condition: task.risk_tier == HIGH
       contributes: 2

TP-06  Shared resource coupling
       condition: SDG has ≥1 edge with kind="shared_resource" AND blocking=True
       contributes: 2
       advisory-only shared_resource edges do NOT fire TP-06

TP-07  Deep dependency DAG
       condition: topological height of blocking SDG ≥ 5
       contributes: 3

TP-08  Default / large fan-out pressure
       condition: always evaluated when no hard gate fired
       contributes: ceil(sqrt(subtask_count)) if subtask_count ≥ 8 else 4

max_wave_width = min(candidates ∪ {contributions from TP-05..TP-08 that match})
# TP-08 always matches in the soft phase, so there is always a finite soft value.
policy_rules_fired = [hard id] OR [each soft id whose contribution equals the min among soft+profile candidates]
```

#### Final-width formula (the only width math)

Four numbers exist. They are **not** four independent schedules. They compose as:

```
profile_bound       = min(profile.max_parallelism, ctx.max_parallel_impl_agents)
tp_width            = 1 if a hard gate fired else min(soft contributions ∪ {profile_bound})
max_wave_width      = tp_width   # stored on ExecutionPlan; Step 5 splits levels to this cap
dispatch_concurrency = min(max_wave_width, fleet_available, remaining_budget_workers)
                     # runtime only; does NOT change ExecutionPlan.waves

width_cap_source = (
  f"final={max_wave_width}"
  f"|profile={profile.max_parallelism}"
  f"|ctx={ctx.max_parallel_impl_agents}"
  f"|hard={hard_id or 'none'}"
  f"|soft={'+'.join(f'{id}:{n}' for each matching soft cap)}"
)
```

If `profile.execution_order == "sequential"` (hotfix Rule 2, §F.3), treat as an extra hard gate **before** TP-01…TP-08: `max_wave_width = 1`, `hard=profile.execution_order`. `WorkflowProfile.execution_order` is an existing workflow scheduling preference / hotfix gate — **not** `ExecutionPlan.topology_class` (derived label). Keep the field name for compatibility; do not rename or replace it with `topology_class`.

**What TP rules may / may not do:**

| May | Must not |
|---|---|
| Cap / reduce `max_wave_width` | Remove or ignore a blocking SDG edge |
| Force serialization (width 1) via hard gate | Invent new subtasks |
| Cause Step 5 to split an independent level | Call an LLM |
| Record into `TopologyDecisionRecord` | Override `profile_bound` upward |

**DAG correctness vs TP conservatism:** Steps 1–2–4 are correctness. Step 3 + Step 5 are scheduling policy. A blocking edge always wins over a desire for width.

#### `topology_class` derivation (exact)

```
blocking = SDG has ≥1 blocking edge
widths = [w.width for w in waves]

if all(w == 1 for w in widths):
    topology_class = "sequential"
elif not blocking:
    # Independent set only — including the case where Step 5 split a wide
    # independent level under a width cap. Still "parallel" for evaluation:
    # no dependency-forced serialization occurred.
    topology_class = "parallel"
elif len(waves) == 1:
    topology_class = "parallel"
else:
    topology_class = "hybrid"
```

This removes the ambiguity where width-cap splits incorrectly looked like hybrid dependency structure.

#### Concrete SDLC validation example

Task: soft-delete Users. `risk_tier=MEDIUM`, `confidence_score=0.85`, `repo_scale=large`, `profile.max_parallelism=5`, `max_parallel_impl_agents=5`, RI up.

Subtasks: A=migration, B=model (dep A), C=repo (dep B), D=API (dep C), E=admin UI (independent).

```
Hard gates: none
Soft: TP-08 → 4; profile_bound=5 → max_wave_width=4
Levels: L0={A,E} L1={B} L2={C} L3={D}
Waves: [A,E] [B] [C] [D] → topology_class=hybrid
policy_rules_fired=["TP-08"]
```

If `risk_tier=CRITICAL` → TP-03 → all width 1 → sequential.  
If RI down → TP-01 → sequential.  
If `risk_tier=HIGH` → soft min(5,2,4)=2 → L0 may become [A][E] if both present, etc.

#### D.10.3.1 TP rules are configuration, not LLM and not code-scattered magic numbers

**What a TP rule is:** a named, ordered, deterministic predicate that contributes to `max_wave_width`. It is **not** an agent, **not** a LangGraph node, and **not** a model call.

**Who defines it:** platform policy in `configs/topology_policy.yaml` selected by `WorkflowProfile.topology_policy_id` (default `"default"`). The evaluator is `packages/orchestration/topology_policy.py` — pure functions. Engineers change thresholds in YAML; they do not prompt an LLM.

**When it executes:** only inside `plan_execution_waves()` Step 3 — at initial plan, and again on amendment/demotion re-levelize of **remaining** work (hard gates still apply; width must not increase vs the attempt's original `max_wave_width`).

**What it reads:** Task, WorkflowContext, WorkflowProfile, SDG — already on `SDLCState` / injected adapters. Zero LLM.

**What it changes:** `max_wave_width` only (then Step 5 may split levels).

**What it cannot change:** SDG edges, subtask list, `topology_class` (derived later), git, WCP.

**DAG interaction:** blocking edges always win. TP never deletes an edge. A width cap cannot co-schedule a predecessor with its successor.

**`max_parallelism` interaction:**
```
profile_bound = min(profile.max_parallelism, ctx.max_parallel_impl_agents)
max_wave_width = min(profile_bound, tp_result)
```
TP cannot raise the profile bound.

**Invariant (not YAML-overridable):** TP-01 (RI unavailable → width 1) and "amendments never widen" cannot be disabled. A policy file that sets `allow_parallel_without_ri: true` is a load-time validation error.

**Additional hard gate from existing workflow engine (not a new LLM):** included in the final-width formula above (`profile.execution_order == "sequential"`).

Default YAML (numbers match the TP ladder above):

```yaml
# configs/topology_policy.yaml
id: default
hard_gates:
  tp01_ri_unavailable: { enabled: true }          # not overridable to false
  tp02_confidence_floor: 0.70
  tp03_critical_width1: true
  tp04_small_repo_width1: true
soft_caps:
  tp05_high_risk_width: 2
  tp06_shared_resource_width: 2
  tp07_deep_dag: { height_threshold: 5, width: 3 }
  tp08_default_width: 4
  tp08_sqrt_fanout_from: 8
```

Phase 15 may ship alternate files (`conservative.yaml`, `throughput.yaml`) behind `topology_policy_id`. Changing a file is an **experiment** (§L.8): bump `orchestration_version`, replay golden set. The selector remains deterministic given (decomposition, SDG, profile, ctx, task, policy file).

---

### D.10.4 Dispatch concurrency vs. plan width

**These are two separate numbers.** `ExecutionWave.width` is the number of sub-tasks *allowed* to run in parallel according to the dependency plan — it is determined ahead of time and recorded in the `TopologyDecisionRecord`. `ExecutionPlan.dispatch_concurrency` is the number that actually run simultaneously at the moment the Wave Scheduler dispatches a wave — it is set at runtime and constrained by agent fleet capacity, the `Task.budget.token_ceiling`, and kill-switch state.

`dispatch_concurrency ≤ width` always. Reducing `dispatch_concurrency` for capacity reasons does **not** change the plan (no plan amendment, no new `TopologyDecisionRecord`), because the plan states independence — independent sub-tasks may be dispatched in any order within a wave. Reducing `width` itself requires a plan amendment (§D.10.5) because it implies a new blocking edge was discovered.

This separation is what makes plans reproducible for evaluation (§L.8): the plan is a deterministic function of the SDG and the policy rules; the concurrency level is an ephemeral runtime detail. Exact composition of `max_wave_width` vs `dispatch_concurrency` is the **final-width formula** in §D.10.3.

Narrowing `max_wave_width` on amendment/replan is allowed (fail-closed). Widening it is forbidden.

### D.10.5 Plan amendment vs demotion vs Manager replan vs escalation

These mechanisms are **not** interchangeable. Demotion is a *subtype* of plan amendment that also supersedes executed attempts.

| Mechanism | Trigger | Owner | LLM? | Changes DAG? | Changes remaining active plan? | Example |
|---|---|---|---|---|---|---|
| **ClarificationEscalation** | Worker cannot safely continue | Worker emits; Fan-in batches | No (emit) | Not by itself | Only after Manager resolves | Missing symbol; broken assumption |
| **Plan amendment** (pure) | New blocking dep affects **only undispatched** subtasks (WCP `discovered_dependencies`) | Fan-in → `plan_execution_waves` on remainder | No | **Add-only** blocking edges | Yes — re-levelize remaining; `plan_version++` | Wave0 discovers E needs C; E not started |
| **Wave demotion** | Conflict among **executed** validated branches in current wave | Fan-in (§D.4.4) | No | Add-only discovered edges | Yes — supersede attempts + rewrite remaining (amendment subtype) | A,B file overlap after both validated |
| **Manager replan** | Escalations / `needs_manager_attention` / amendment cap / cycles / demotion abort / cross-wave vs already-merged | Implementation Manager | **Yes** | May rewrite decomposition (WHAT) | Yes — new plan; completed waves frozen in `ReplanContext` | Circular semantic conflict |

**Amendment invariant (all amendment subtypes):** may only **add** blocking edges, never remove them; may not widen `max_wave_width`; `plan_amendment_count ≤ max_plan_amendments` (default 3) else escalate to Manager replan.

**Completed waves:** never re-levelized, never unmerged by amendment/demotion.

---

### D.10.6 WaveHandoffNote assembly

At the close of wave K, after `merge_eligible` branches have been merged (or skipped if none), the Fan-in Coordinator assembles a `WaveHandoffNote` for wave K+1.

**Assembly algorithm (deterministic, zero LLM calls):**

```
inputs:
  merge_eligible WCPs for sub-tasks in waves 0..K (highest attempt per subtask_id)
  existing WaveHandoffNotes for waves 0..K-1
  # blocked/failed/ignore-keyed attempts are excluded

1. Merge interface_changes across all completed WCPs:
   - Group by symbol_id; on conflict (two sub-tasks both claim a change to the same symbol):
     → retain both entries, mark both with status="conflict", add to unresolved_issues
   - Non-conflicting: deduplicate by symbol_id, keep latest by wave_index

2. Merge files_touched:
   - Union of all touches_files across all completed WCPs
   - Deduplicated

3. Merge discovered_dependencies:
   - Union, deduplicated by symbol_id format

4. Merge constraints_for_next_waves:
   - Collect from WCP.risks (short strings only)
   - Collect from still-open ClarificationEscalation items

5. Priority-truncate to token_budget (§B.5 "wave → wave" row):
   Priority order (highest to lowest):
     a. interface_changes with status="conflict"
     b. unresolved_issues
     c. interface_changes without conflict
     d. constraints_for_next_waves
     e. files_touched (drop to count only if over budget)
     f. discovered_dependencies
   Set truncated=True if any item was dropped; dropped items' Blackboard refs appended to artifact_refs
```

**Default token budget for wave-to-wave handoff:** 2,000 tokens. Rationale: a worker receiving this note needs the interface and constraint delta, not a full project summary. The ledger (§H.5) already provides the authoritative historical record; the note is the *incremental* update from the most-recently-closed waves.

### D.10.7 Repository Intelligence query budget for topology selection

Topology selection must not become a full-repository scan. RI queries in `plan_execution_waves()` are bounded:

| Query type | Budget per call | Max calls per plan |
|---|---|---|
| `get_file_structure(file)` | 1 | `min(50, total_owned_files)` |
| `get_callers(symbol, depth=1)` | 1 | `min(20, total_declared_symbols)` |
| `get_dependents(file)` | 1 | `min(20, total_owned_files)` |
| `get_impact_set(files)` | 1 (batched) | 1 |
| Architecture summary | 1 (cached) | 1 |

Total RI calls capped at 50 per plan. If the sub-task count or symbol count would require more, sample the highest-risk pairs (by declared dependency count) and flag the unqueried pairs as `advisory` edges rather than `confirmed`. This preserves the Fail-Closed property: unconfirmed edges are treated as if they exist, making the schedule more conservative, not more aggressive.

### D.10.8 Sub-agent spawning — rejected for MVP and Phase 2

**Decision:** worker-spawned sub-agents are not supported.

**Problem it claims to solve:** a sub-task too large for one worker.

**Why rejected:**

- The problem is already solved at zero architectural cost. If a sub-task is too large, the worker raises `ClarificationEscalation(category="scope_ambiguity")` and the Manager re-decomposes the sub-task into finer-grained items in the next wave. This is exactly the "Worker discovers a sub-task needs to be split" case — handled by the existing escalation + replan path.
- Worker-spawned sub-agents break `max_parallelism` enforcement. Only Wave Scheduler may `Send`; uncontrolled recursive spawning makes width caps meaningless.
- Depth-2 hierarchies (Manager → Worker) already carry a coordination penalty. Depth-3 (Manager → Worker → Sub-Worker) multiplies that penalty.
- Attribution accuracy at depth-3 would fall further below the already-concerning 53.5% (manager + tool attribution) and 14.2% (step attribution) figures cited in the empirical literature.

**Future:** if depth-3 delegation is added, it must be bounded at every level: `max_depth=2` (current level), `max_children=3`, budget propagation (child budget ≤ remaining parent budget), and scope restriction (child may only operate within its parent worker's assigned file/symbol scope). This is a Phase 3 item, gated on Phase 15 evaluation data showing that the current escalation path is a genuine throughput bottleneck.

### D.10.9 Fail-Closed behaviour for topology selection

**If `plan_execution_waves()` cannot complete safely, the schedule defaults to fully sequential (width 1 for all waves).** This is the Principle 8 (§A.2) application to topology: an uncertain plan narrows parallelism, never widens it.

Specific triggers:

| Condition | Fail-Closed behaviour |
|---|---|
| RI unavailable or timeout during dependency verification | `sdg.ri_available=False`; set all unverified edges to `blocking=True`; `topology_class=sequential` |
| Cycle detected in SDG | Escalate to Manager replan; if replan also produces a cycle: HITL. Never dispatch a cyclic plan. |
| `plan_amendment_count` cap exceeded | Escalate to Manager replan |
| `task.risk_tier == CRITICAL` | Width cap = 1 (hard gate TP-03) |
| `confidence_score is None or < 0.70` | Width cap = 1 (hard gate TP-02) |
| Any `SubtaskDependencyEdge` fails schema validation | Treat as blocking edge (Fail-Closed) |

---



## D.10.10 Multi-wave lifecycle — developer walkthrough

### What creates Wave 0
`plan_execution_waves` emits `ExecutionPlan.waves[0]`. Wave Scheduler sets `current_wave_index=0` and returns `Send` for each id in that wave (subject to `dispatch_concurrency`).

### What makes a wave complete
Every branch in the wave has terminal `ImplementationResult` with status in `{validated, blocked, failed}` (retries finished). Mid-FL-04 does not complete the wave.

### Fan-in before next wave
Runs decisions 1–10 (§D.4.1): select → intra/cross checks → merge eligible → demote/amend if needed → assemble `WaveHandoffNote` → advance index or exit.

### State carried forward
- Git: integration worktree HEAD
- Notes: latest `WaveHandoffNote` for `for_wave = next`
- Ledger: Context Ledger entries (T1)
- Plan: active `ExecutionPlan` at current `plan_version`
- Not carried as prompt bulk: raw diffs, full WCP lists, tool traces

### Worker failure
FL-04 on that branch; siblings continue; Fan-in waits for terminal states.

### Dependency discovered (undispatched only)
Pure plan amendment (§D.10.5).

### Conflict discovered among executed peers
Wave demotion SM (§D.4.4).

### Cycle detected
At planning or demotion orient: Manager replan; else HITL. Never dispatch cyclic active plan.

### Example A — Pure parallel
Subtasks A,B,C independent; RI confirms; soft cap width≥3.
Active plan: `Wave0=[A,B,C]`, `topology_class=parallel`.
One Fan-in; one WaveHandoffNote (optional if no further waves); Integration Validator.

### Example B — Pure sequential
A→B→C blocking chain (or hard gate TP-01/02/03/04).
Active plan: `[A][B][C]`, `topology_class=sequential`.
After A merges, B receives WaveHandoffNote covering wave 0; base = integration HEAD.

### Example C — Hybrid
A=migration, B=model(dep A), C=API(dep B), D=UI(independent), E=docs(independent).
Waves: `[A,D,E] → [B] → [C]` (if width cap ≥3), `topology_class=hybrid`.

### Example D — Demotion
Planned `Wave0=[A,B]`; both validate; file overlap.
History: demotion event; attempts superseded.
Active plan becomes `[A]→[B]` with discovered edge; not `[A,B]+[B]`.

---


## D.10.11 LLM call budget — layers are not extra model calls

**Challenge the diagram.** `Manager → DAG → Topology Selector → Wave Scheduler` is a *data-flow*, not four agents. Treating each box as an LLM would multiply cost with no quality gain. This section is the production call architecture.

### Comparison (choose B)

| Option | Happy-path Implementation LLMs (excluding CodeGen workers) | Verdict |
|---|---|---|
| **A. Naive reading of four boxes** | Manager + topology LLM + scheduler LLM + fan-in LLM | Reject. Fan-in/scheduler have no judgment that a model improves. |
| **B. One Manager structured call + deterministic topology (CHOSEN)** | **1** High-capability structured-output call | Matches Principle 5; same LLM count as V3.0 Manager decomposition |
| **C. Manager + LLM topology planner** | 2 High-capability calls | Reject. Topology is a graph algorithm. A second model would be untestable, non-reproducible, and empirically worse at "who may run with whom" than RI + TP policy (CooperBench: comms don't fix semantic coordination). |
| **D. Manager ReAct loop that also queries RI then "decides" waves** | 1 call *plus* N tool-round-trips (often 5–15 extra LLM steps) | Reject as default. RI queries belong in Python. ReAct burns tokens re-deriving `get_callers` the selector already runs on a budget. |

**Chosen: B.** The DAG/hybrid design adds **zero** happy-path LLM calls versus V3.0. It adds CPU (topo-sort, RI lookups, Fan-in).

### What MUST use an LLM vs what MUST NOT

| Component | LLM? | Why |
|---|---|---|
| Implementation Manager **initial decompose** | **Yes — exactly one structured call** | Inventing subtasks/scopes is a reasoning job. Output schema = `TaskDecomposition` only. |
| Manager RI tool loop during decompose | **No (default)** | Inject L0 architecture summary + design packet into the prompt; do **not** give the Manager `get_callers`/`get_dependents` as tools on this call. Selector verifies. |
| DAG construction / RI verify / overlap | **No** | Tree-sitter + RI point lookups (§D.10.7). |
| TP-01…TP-08 | **No** | Config-driven deterministic policy (§D.10.3.1). |
| `plan_execution_waves` / topology_class | **No** | Pure function. |
| Wave Scheduler / `Send` | **No** | LangGraph control flow. |
| Fan-in, demotion, amendment, WaveHandoffNote | **No** | Deterministic. |
| `Validator`(implementation) | **No** | Tools only. |
| CodeGen × wave width | **Yes — one worker trajectory per subtask** | Unavoidable. WCP fields MUST be the same structured call as the diff (§D.9.2), not a second round-trip. |
| Integration Validator | **Yes — one High-capability call with tools, once after last wave** | Needs judgment over merged contracts; tools do caller/test checks first. Not per wave. |
| Manager **replan** | **Yes — at most one per wave per attempt**, only on escalation/cycle/amendment-cap | Do not replan to "pick a topology." |
| Feedback Agent | **Yes — only after FL-04 ×3** | Already bounded. |
| T3 compaction summarizer | **Yes — last resort** (Phase 12), wave-boundary, never for T1 ledger | Deterministic T2 clear first. |
| WaveHandoffNote / Context Ledger extract | **No** | Projection from typed WCP/state. |
| Confidence / risk_tier for TP | **No extra call** | `Task.confidence_score` is §B.4 formula; `Task.risk_tier` is intake. Manager MUST NOT invent replacements. |

### Manager: one structured output (WHAT only)

The Implementation Manager node runs as:

```
1. Assemble prompt (no tools):
     ArchitectureDoc + PhaseHandoffPacket (Design→Implementation)
     + L0 architecture summary (cached RI, not a tool loop)
     + Task.risk_tier, Task.confidence_score (read-only context, not for the model to overwrite)
2. ONE High-capability structured-output invocation → TaskDecomposition:
     tasks[]: id, description, module, target_files, declared_dependencies, model_tier_hint
     ownership_map
     version
   Optional per-subtask fields allowed: estimated_complexity (advisory ONLY for model_tier_hint)
   Forbidden outputs: topology_class, waves, max_wave_width, execution_order-as-schedule,
                      confidence_score, risk_tier
3. Python immediately calls plan_execution_waves(...)  # same graph node, zero extra LLM
4. Write ExecutionPlan + TopologyDecisionRecord to SDLCState
5. Return — Wave Scheduler issues Send on the next superstep
```

**Do not** combine Manager+CodeGen into one call: that destroys isolation, WCP, worktrees, and parallel width.

**Do not** ask the Manager for a "risk estimate" that overrides `Task.risk_tier`. Complexity may only choose Fast vs High-capability **per subtask** (`model_tier_hint`); TP rules ignore complexity (Principle 10).

### Happy-path call count (normal Development implementation attempt)

Assume hybrid plan, 3 CodeGen subtasks, all pass Validator first try, no escalation:

| # | Call | Tier |
|---|---|---|
| 1 | Implementation Manager structured decompose | High-capability × 1 |
| 2–4 | CodeGen (one trajectory each; WCP in same call) | Fast or High × 3 |
| 5 | Integration Validator | High-capability × 1 |

**Total: 5 LLM trajectories.** Topology, TP, DAG, Scheduler, Fan-in, handoff: **0**.

V3.0 parallel-only with 3 workers was also ~1 Manager + 3 CodeGen + 1 Integration Validator. Hybrid adds CPU, not models.

Conditional extras (not happy path): FL-04 retries, Feedback Agent, Manager replan, MASC Check 3 (fast, `implementation_plan` only), Phase 12 T3 summarizer.

### Large-repo cost control

- Manager prompt: L0 + design packet — never the 100k-file graph.
- RI in selector: ≤50 point queries (§D.10.7), advisory-blocking if over budget.
- Workers: progressive tools, WaveHandoffNote ≤2k, ledger T1, not previous diffs.

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
- **Managers hold coordination authority; Wave Scheduler holds mechanical `Send` (§D.9.5).** A sub-agent that discovers it needs help raises a `ClarificationEscalation` (§D.9.3) and stops its own branch — it never spawns a helper worker, delegates to a peer, or reassigns scope itself.



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
| **Implementation Manager**  | **One** structured-output LLM call: TaskDecomposition (WHAT). Then **Python** `plan_execution_waves()` in the same node. No RI tool loop on this call. Coordination authority only (§D.9.5). | Approved design + L0 summary + handoff packet → TaskDecomposition; selector writes ExecutionPlan | High-capability **×1** (happy path) | **None on decompose call.** RI is injected into the selector, not the Manager. | Exit: cycle-free SDG after selector. Failure: cycle / schema fail → bounded replan (second LLM) or HITL |
| **Topology Selector**       | Deterministic `plan_execution_waves` + TP policy YAML (§D.10.3) | TaskDecomposition + RI + profile + ctx + task → ExecutionPlan | — | RI point lookups (§D.10.7) | Same node as Manager after LLM returns; not a separate agent |
| **Wave Scheduler**          | Mechanical `Send` per active wave (§D.9.5) | ExecutionPlan.waves[i] → Send[] | — | None | Not an LLM |
| **CodeGen Sub-agent (×N)**  | Implements one module/scope per instance (parallel via Send API); emits `WorkerCoordinationPacket` on exit (§D.9.2), or `ClarificationEscalation` + stops (§D.9.3) if blocked | Module spec + progressive context → diff + WCP                | Fast (simple) / High-capability (complex refactor) | `get_symbol_signature`, `get_symbol_body`, `get_callers`, `get_file_structure`, sandbox | Exit: diff + WCP produced; self-check clean. Failure 3×: Feedback Agent. Never contacts another CodeGen instance directly (§D.9.1) |
| **Fan-in Coordinator**      | Deterministic (not an agent, not an LLM) — per-wave boundary §D.4.1 | Branch diffs + WCPs → merge / demotion / amendment / handoff | — (no model call) | File-set/diff analysis, WCP fields, RI caller cross-check (tools, not LLM) | Exit: clean merge or demotion/replan. Never silently auto-merges |
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
    # Existing workflow scheduling preference / hotfix gate (e.g. Rule 2 → "sequential").
    # Kept for compatibility. NOT ExecutionPlan.topology_class.
    # Topology Selector: if "sequential" → hard width-1 gate only (§D.10.3).
    qa_depth: Literal["minimal", "standard", "deep", "exhaustive"]
    model_tier: Literal["fast_cheap", "balanced", "frontier"]
    approval_requirements: list[Checkpoint]
    max_parallelism: int              # capped by repo_scale (§F.2)
    cost_budget_usd: float            # derived from risk tier and work type
    topology_policy_id: str = "default"  # key into configs/topology_policy.yaml (§D.10.3.1)

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
            topology_policy_id="default",
        )
```

`topology_policy_id` selects `configs/topology_policy.yaml` (schema §D.10.3.1). Phase 10 may point different risk/work-types at different policy files; evaluation never requires an LLM to choose a policy — `resolve_workflow_profile()` already returns the profile.

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
        profile.execution_order = "sequential"
        profile.qa_depth = STANDARD_PLUS_BUG_VALIDATION
        return profile
    
    # Rule 3 — Low confidence (or scorer failed): escalate regardless of risk tier
    # CONFIDENCE_FLOOR = workflow-routing approval gate (policy constant). Distinct from:
    #   TP-02 topology width gate (0.70) and §B.4 Implementation floor (0.75 model-tier).
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
| **L0** | Raw files on the local working tree             | Explicit `index` / `reindex`; SHA-256 catalog (git hooks deferred) |
| **L1** | AST/symbol index (Tree-sitter)                  | Incremental, per changed file                                      |
| **L2** | Dependency/call graph (NetworkX→Neo4j)          | Incremental, changed file only (dependents are query-time)         |
| **L3** | Semantic embeddings (pgvector→Qdrant)           | Incremental, chunks whose content_hash changed                     |
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

**MVP source of truth:** the local working tree under `repo_root` (files on disk, including uncommitted edits), not git HEAD. See `docs/phases/phase-03/section-05.md`.

- Content-hash-triggered re-indexing scoped to files whose SHA-256 changed (create / modify / delete). Do **not** re-index 1–2 hop dependents; `get_impact_set` is a graph **query**.
- Retrieval fail-closes (`StaleIndexError`) if the catalog lags the working tree. Explicit `reindex` (or `refresh=True`); no silent stale answers.
- **Nightly full re-index** and **git hooks** are deferred (not required for MVP freshness).
- L4 summaries invalidated via content-hash + dependency-hash keys (staleness is detectable, not silent).
- Target incremental update latency: < 10s for a typical working-tree change (1–20 files).



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
| RI timeout / unavailable | Fan-in semantic cross-check (§D.4.1.1 step 4) | Treat as conflict → wave demotion if `|C|≥2`, else Manager replan |
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

The Aider codebase established a highly effective technique: build a map of the repo's most important files and symbols by computing PageRank over the codebase's **import/reference graph**. A file that is referenced by other *important* files ranks higher than one that is merely popular among leaves. That map is a dense, token-efficient overview of what matters — typically **~1,000–3,000 tokens** — instead of dumping files or LLM-summarizing the repo.

**Critical refinement for this platform:** we do **not** inject a global “top files in the monorepo” map. Global PageRank on 100k files is nearly useless for a concrete task. We run **Personalized PageRank (PPR)** biased toward a **task seed set** derived from the current goal / input. Seeds pull probability mass toward the neighborhood that matters for *this* issue, wave, or agent; the map answers “given what we already know about this task, which nearby files/symbols should the model orient on?”

### H.2.1 Graph we rank over

| Element | Source | Notes |
|---|---|---|
| Nodes | Files (primary); optionally symbols for finer maps | File-level first; symbol-level only if token budget allows |
| Directed edges | Import / `calls` / `references` from RI dependency graph | Same graph Phase 03 indexes and Phase 11 stores in Neo4j |
| Edge weight | Default 1.0; optional boost for `calls` over weak `imports` | Keep v1 simple (unweighted) unless measured otherwise |
| Scope | Per-shard subgraph containing seeds + k-hop closure | Never run PPR over the full federated graph |

### H.2.2 From goal/input → seed set (this is how relevance enters)

The Context Builder builds `RepoMapRequest` **once per agent invocation** (and again when seeds materially change: new wave, new WCP file list, localisation pass completes). Seeds are the only place task semantics enter PageRank.

```
SeedCollection (ordered, de-duped, capped at N_seed_max = 12):

  S1. Explicit paths in the task envelope
      - Files / symbols named in the ticket, PR description, or ClarificationEscalation answers
      - Paths listed in the current PhaseHandoffPacket / WaveHandoffNote / WCP

  S2. Grep/glob hits from the mandatory first sweep (§H.7 step 1)
      - Exact identifiers, error strings, API names extracted from the goal text
      - Top matches only (cap ~8); prefer source over tests unless QA phase

  S3. Already-touched files this run
      - Files modified in prior waves of this task
      - Files in SDLCState.context_ledger with type=interface_contract | discovered_fact

  S4. Localisation / impact hints (when available)
      - Implementation Manager localisation candidates (§H.7 step 4)
      - get_impact_set() of S1∪S3 (1-hop dependents) for QA / Dependency Impact Agent

  S5. Fallback if S1–S4 empty
      - Shard entrypoints from L0 architecture summary (package roots, main modules)
      - Document as low-confidence; widen map K slightly
```

**Seed weighting (personalization vector `v`):** each seed `s` gets mass `w(s)`, then `v` is L1-normalized over all graph nodes (non-seeds = 0).

| Source | Relative weight | Rationale |
|---|---|---|
| S1 explicit paths | 1.0 | Highest trust — human/goal named them |
| S3 already-touched | 0.8 | Proven relevant this run |
| S4 impact / localisation | 0.6 | Structural relevance |
| S2 grep hits | 0.5 | High precision but can be noisy |
| S5 architecture fallback | 0.2 | Orientation only |

### H.2.3 Personalized PageRank → ranked files

```text
G      = directed dependency graph for shard(s) covering SeedCollection
v      = personalization vector from §H.2.2 (nonzero only on seeds)
α      = damping = 0.85          # standard; teleport weight = 1−α toward v
score  = PPR(G, v, α)            # Neo4j GDS or networkx.pagerank(personalization=v)

ranked = sort files by score desc
       exclude: generated/, vendor/, pure lockfiles (configurable denylist)
       prefer: production sources; demote tests unless agent_phase ∈ {qa, advanced_qa}

top_K  = pack until token budget B_map exhausted (§H.2.5), else K_default = 30
```

**Why this matches the goal:** teleport restarts always jump back to the seed set, so probability mass concentrates on files that are *structurally close to the goal’s anchors*, not merely globally central. A widely-imported `utils.py` far from the seed neighborhood loses to a mid-degree module on the path between two seeds.

**Implementation entrypoint** (`packages/repo_intel/summaries/repo_map.py`):

```python
async def get_aider_repo_map(
    self,
    scope: list[str],                    # seed paths and/or shard ids
    *,
    goal_text: str | None = None,        # used only if caller wants RI to run seed extraction
    seeds: SeedCollection | None = None, # preferred: Context Builder passes explicit seeds
    budget_tokens: int = 2500,
    agent_phase: str = "implementation",
) -> RepoMap:  # { files: [{path, score, symbols:[{name, signature}]}], token_estimate, seed_ids }
```

Phase 03 keeps a stub (raw in-degree). Phase 12 replaces the body with real PPR; callers already use this signature.

### H.2.4 Render map (what the model actually sees)

For each file in `top_K`, attach **skeletal symbols only** (Tree-sitter signatures + one-line docstring), never bodies:

```text
# Repo map (personalized PageRank | seeds: auth/service.py, api/routes/user.py)
auth/service.py                          score=0.142
  class AuthService
  def authenticate(user_id: str, token: str) -> Session
  def revoke_session(session_id: str) -> None
api/routes/user.py                       score=0.091
  def delete_user(user_id: str) -> None
db/models/user.py                        score=0.067
  class User(Base)
...
```

Agents treat this as an **orientation index**, then expand with `get_symbol_body` / `get_callers` / `search_codebase` (§H.4). Bodies are never in the map.

### H.2.5 Exact fit in the platform flow

**Where it sits in prompt assembly (§M.2 / §H.6):**

```text
T0  System prompt + tools + L0 architecture summary     (stable KV-cache prefix)
    └── L0.5 Repo map (this section)                    (task-scoped; rebuild when seeds change)
T1  Context ledger (pinned)
T2  Working window (task spec, recent tools, …)
…   Phase Handoff Packet pointer / excerpts as designed
```

Injection order inside the agent message remains:

1. Architecture summary (L0)
2. **Aider repo map for task scope (L0.5)** ← Context Builder calls `get_aider_repo_map`
3. Phase Handoff Packet
4. Task-specific retrieved context (RRF / grep windows / progressive tools)

**When it runs (per phase):**

| Phase / agent | Seed bias | Map role |
|---|---|---|
| Design Manager / Repo Architecture Analyst | S1 ticket paths + S2 concept grep + L0 packages | Orient design on real modules before ADR/pattern retrieval |
| Implementation Manager (pre-dispatch localisation) | S1 + S2 + prior-wave files | Produce candidate edit surface; feeds Worker WCPs |
| CodeGen / Worker agents | WCP `target_files` + interface_contract ledger entries | Every worker starts knowing the neighborhood of *its* edit set |
| Dependency Impact / QA | Changed files in diff + `get_impact_set` | Rank regression blast radius for test selection |
| Security / Advanced QA | Same as QA + SAST entry hits | Prefer high-PPR files in the change neighborhood |

**Orchestration sequence (implementation / coding path):**

```text
1. Task arrives → extract goal text + explicit paths into TaskEnvelope
2. Context Builder:
     a. Grep/glob sweep on goal identifiers          → S2
     b. Merge S1–S4 into SeedCollection
     c. RI.get_aider_repo_map(seeds=…, budget=B_map) → L0.5 string
     d. Assemble prompt: L0 → L0.5 → handoff → task spec
3. Implementation Manager localisation (§H.7.4) may add seeds → rebuild map once
4. Wave Scheduler / workers:
     - Each worker gets a map personalized to its WCP target_files (not the global task map)
5. Mid-task: if worker discovers a new hub file (ledger discovered_fact), optionally
   refresh L0.5 once per wave — not every tool call
6. Downstream: RRF fusion (§H.7.3) may re-rank retrieval candidates using
   PPR scores as one fused list (map injection and RRF scoring share the same score cache)
```

**Budget packing:**

- Default `B_map`: design = 5000 (see `PHASE_BUDGETS`), implementation workers = 1500–2500, QA = 2000.
- Pack highest-score files first; stop when adding the next file’s signatures would exceed `B_map`.
- If a single file’s symbol list is huge, keep only the top symbols by in-file reference count (or export surface).

**Non-goals / hard rules:**

- Do not substitute the map for localisation — it orients; grep + skeleton localisation still pick edit sites.
- Do not dump PPR scores into the ledger unless a file becomes an interface contract.
- Do not recompute full-shard PPR every tool call — cache scores keyed by `(shard_graph_version, frozenset(seeds), α)` until incremental index bumps the graph version.

### H.2.6 Success signal

- Map alone (no file bodies) lets Design/Implementation agents name the correct modules in first-pass plans ≥ baseline with global/in-degree map.
- Token cost of L0.5 stays within budget band; Phase 12 gate: average tokens/task ↓ ≥ 40% vs Phase 11 with no success-rate drop (map is one contributor alongside §H.1/§H.3/handoff packets).



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

## H.5 Context Ledger — lossless, pinned critical facts

**Why it exists.** Production compaction studies (Factory.ai, 36 k-message production dataset) score artifact tracking 2.19–2.45 / 5.0 *across every published method*. The study's diagnosis: "a file path may be 'low entropy' from an information-theoretic perspective, but it is exactly what the agent needs to continue working." Rather than hoping a smarter summariser one day solves this, we extract critical facts into an append-only, typed, provenance-bearing ledger that lives *outside* the compressible tier entirely.

`ContextLedgerEntry` schema is defined in §B.2. The ledger is stored in `SDLCState.context_ledger` (an `append_only` `DeltaChannel`) and is rendered verbatim into every agent prompt in the pinned T1 slot (§H.6). It is never fed into a compaction call.

**What belongs in the ledger (mandatory):**
- Decisions — what was chosen and a brief rationale
- Constraints — hard "must / must-not" requirements for this task
- Interface contracts — exact symbols, signatures, or protocols that workers must honour
- Discovered facts — net-new information from RI, RI failures, or escalations
- Unresolved issues — open `ClarificationEscalation` IDs with a short question
- Validation outcomes — failures that have already occurred, so workers do not repeat dead approaches
- WCP-extracted interface changes (§D.9.2) — authoritative record of what was changed, by whom

**What does NOT belong** (stays in the compressible T2/T3 tiers):
- Full tool results (Blackboard pointer suffices)
- Raw diff content
- Routine log lines

**Eviction policy.** When `SDLCState.context_ledger` grows past its configured cap (default 200 entries), entries with `status="superseded"` or `status="resolved"` are evicted first, with their Blackboard pointers retained in a compact eviction log. `status="active"` entries are never evicted automatically.

## H.6 Compaction tiers and triggers

**Five-tier prompt layout.**

| Tier | What lives here | Compressible? | Trigger |
|---|---|---|---|
| **T0 — Stable prefix** | System prompt, tool definitions, architecture summary (L0), invariant conventions | Never | Never modified — KV-cache anchor |
| **T1 — Pinned ledger** | `SDLCState.context_ledger` entries; current `WaveHandoffNote` only (not full note history) | Never | Never — rendered verbatim after T0. On wave advance, replace the pinned note with the new `for_wave` note; prior notes remain in append-only state / Blackboard refs, not in the prompt. |
| **T2 — Working window** | Recent tool results (last N), current sub-task spec, task envelope | Tier-2 clearing | Wave boundary or token pressure ≥ 40 % of usable budget |
| **T3 — Compacted history** | Anchored structured summary of evicted T2 spans | Lossy (but restorable) | Wave boundary or token pressure ≥ 70 % of usable budget |
| **T4 — Blackboard** | Diffs, logs, raw traces, evicted spans, `PhaseHandoffPacket`, evidence bundles | Never | Referenced by pointer only; never inlined |

**Compaction rules (derived from production evidence):**

1. **Wave-boundary first.** The preferred trigger for T3 compaction is the completion of a wave, not a token threshold. A wave close is the first moment a coherent, completed unit exists — the summariser sees a finished thought rather than a mid-task state. This is implemented as an explicit `compact_at_wave_close` flag in the Wave Scheduler node (§D.4.0), not as a reactive token check.

2. **Multi-signal threshold for intra-wave compaction.** If compaction must fire mid-wave (long single-wave runs), require *both* a token signal *and* a recency signal: e.g. token pressure ≥ 70 % of usable AND at least one completed tool-use group (search → read → analyse) has accumulated. Prevents compacting before the worker has enough context to be useful.

3. **Tier-2 clearing precedes tier-3.** Before any LLM compaction call runs, the T2 clearing pass removes tool results older than the last-N window. This is deterministic, free, and preserves the KV-cache prefix because it only removes from the tail.

4. **Never compact into an empty T1.** If the ledger is empty when T3 fires, extract the minimum critical facts (interface changes, constraints) from the T3 span before summarising it.

5. **Anchored-iterative merge, never regenerate.** The T3 summary is a persistent structured document with explicit sections (session intent, modified files, decisions, next steps, open issues). When T3 fires again, *only the newly evicted span is summarised and merged into the existing summary* — the existing sections persist by reference. This prevents compounding loss across multiple compaction cycles.

6. **Every eviction produces a Blackboard pointer.** No information is discarded without a restorable reference. The Blackboard pointer and a one-line digest are appended to the T3 summary, enabling any agent to re-expand the original content via a tool call.

7. **JSON serialisation for KV-cache stability.** WCPs, ledger entries, and any structured data rendered into prompts must use canonical, sorted-key, stable-field-order JSON. A single non-deterministic field (e.g. a timestamp in the stable prefix) can invalidate the entire prefix cache and convert a 10× cache discount into full-price input tokens.

**Tokens-per-task, not tokens-per-request.** The correct efficiency metric is total tokens consumed across all LLM calls to successfully complete a task, not the size of any individual call. A well-sized context that eliminates one re-fetching loop is cheaper than a stripped-down context that forces three extra tool calls.

## H.7 Retrieval strategy for large repositories (100k+ files)

**Hybrid, grep-first, personalized PageRank for budgeted packing.**

For a 100k-file repository, no single retrieval mechanism is universally best. The recommended hybrid:

1. **Grep/glob as the primary cursor** — always fresh, zero staleness, high precision on exact identifiers, error strings, and symbol names. Use windowed reads (cap at ~50–100 lines) rather than full-file reads.

2. **Personalized PageRank repo map for each task** (§H.2) — full seed → PPR → L0.5 injection flow is specified in §H.2.2–H.2.5. Summary: bias the teleport vector on the task's seed files (explicit paths, grep hits, prior-wave edits, localisation/impact hints), rank the shard subgraph, inject top-K file+signature skeletons after L0. A global repo map of 100k files at 1k tokens is close to useless; a personalized map seeded on ~5–12 highly-relevant files is exactly what PageRank is designed for. Best budgeted context yield — most gold content per token — of any retrieval method studied.

3. **Embedding / semantic retrieval via RRF fusion** — add on top of (2) for vocabulary-mismatch cases (e.g. "delete user" → `deactivate_account`). Reciprocal-rank fusion of PageRank map + pgvector results consistently outperforms either alone.

4. **Agentless-style hierarchical localisation in worker context (not a second Send path).** Before CodeGen runs, assemble edit locations via grep/glob → candidate files → skeleton view (signatures, no bodies) → fine-grained locations. Workers receive skeletons of candidates plus full bodies only for precise locations. This is **context assembly**, not scheduling: mechanical `Send` remains Wave Scheduler–only (§D.9.5). This follows the empirically-validated finding that full-file injection *hurt* localisation accuracy compared to skeleton injection.

5. **Never load the full dependency graph into context.** RI queries are point lookups (`get_callers`, `get_dependents`) against the shared long-lived RI service. Topology information for the task is summarised in the L0 architecture JSON and in the SDG's edge list (§B.2), not by dumping the whole NetworkX graph.

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
| MANAGER | Replan cap honored (≤1 per wave per attempt) | Deterministic | **MVP** |
| MANAGER | Happy-path Implementation LLM count = 1 Manager + N CodeGen + 1 Integration Validator | Deterministic (`llm_call` spans; no model_id on selector/scheduler/fan-in) | **MVP** |
| MANAGER | `merge_eligible` never true for ignore-keyed attempts | Deterministic | **MVP** |
| MANAGER | TopologyDecisionRecord present; policy_rules_fired logged | Deterministic | **MVP** (Phase 06) |
| MANAGER | topology_class derivation matches §D.10.3 | Deterministic unit test | **MVP** |
| MANAGER | Demotion rewrites active plan (no live `[A,B]+[B]`) | Deterministic | **MVP** |
| MANAGER | Amendment count ≤ cap; amendments only add edges | Deterministic | **MVP** |
| MANAGER | Unnecessary parallelism (parallel + demotion>0) | Deterministic | **Phase 2** |
| MANAGER | Unnecessary serialization (sequential + zero conflicts + RI available) | Deterministic | **Phase 2** |
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
2. Aider repo map for task scope (L0.5) — Context Builder: goal/input → SeedCollection → Personalized PageRank → top-K file+signature map (§H.2); workers seed from WCP target_files
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
| **6. Live Execution Timeline** | Phase transitions, feedback loops, approvals, waves, amendments, demotions                                                                 | `agent_events` + `topology_decisions` + Fan-in telemetry |
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
│   │   │   └── incremental.py    # Working-tree content-hash re-index
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
│   └── reindex_repo.py           # Working-tree re-index (post_commit_hook.sh deferred)
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