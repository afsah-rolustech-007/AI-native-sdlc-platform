# Architecture Overview

> Source of truth for *what* the system is. `final_plan.md` (the "blueprint") remains the canonical specification for exact schemas, formulas, and tables. This document explains how the pieces fit together and why, in a form suitable for onboarding and for making implementation-order decisions. It does not repeat every field of every schema — see the blueprint section references (e.g. `§B.1`) for exact definitions.

---

## 1. System Vision in One Paragraph

The platform is a semi-autonomous AI software engineering organization-in-a-box. It takes a unit of work (`Task`) — a feature, bug, hotfix, migration, or new project — and moves it through a configurable SDLC (intake → requirements → design → implementation → QA → review → release → monitoring) using LangGraph-orchestrated agents, gated by deterministic policy rules and human approval at irreversible decision points. It is designed to be useful on a 500-file repo on day one and to scale, by strengthening (not replacing) the same architecture, to a 1M+ file enterprise monorepo. Every architectural decision in this document exists to serve one of two goals: **correctness/safety** (fail-closed, validated, auditable) or **incremental buildability** (one engineer can build, test, and demo it in small verifiable steps).

---

## 2. The Five Structural Pillars

Everything in the blueprint reduces to five interacting systems. Understanding these five — and which ones are load-bearing dependencies for the others — is the key to sequencing implementation correctly.

| # | Pillar | Blueprint Ref | One-line Purpose |
|---|--------|---------------|-------------------|
| 1 | **Task & State Model** | §B.1, §B.2 | The durable, queryable, auditable record of a unit of work and its in-flight graph state. |
| 2 | **Orchestration (LangGraph)** | §D | The state machine that moves a Task through phases, with durable checkpoints, interrupts, and rollback. |
| 3 | **Agents** | §E | The narrow-scoped workers (and two reusable templates — `ApprovalGate`, `Validator`) that do the actual reasoning/work inside each phase. |
| 4 | **Repository Intelligence + Memory** | §G, §B.3, §H | The long-lived, cross-task knowledge layer agents query for context — structural, semantic, episodic, procedural. |
| 5 | **Workflow Policy Engine** | §F | The deterministic rule layer that decides *how much* of the above to activate for a given Task (which agents, which QA depth, which model tier, which approvals). |

Two supporting systems cut across all five and are not optional at any phase:

- **Model Abstraction Layer** (§I) — every agent call goes through a `ModelAdapter`, never a provider SDK. This exists from Phase 0 forward because retrofitting it later means touching every agent.
- **Observability / Cost Governance** (§B.7, §B.8) — `TelemetrySink` records Task→Phase→Manager→Agent→LLM/Tool/Validation spans; every token is cost-tracked. OpenTelemetry is the *export* layer, not the application contract. Evaluation (§L) reads telemetry + state, never LangGraph. This exists from Phase 0 because it is the mechanism that makes every later phase debuggable and demoable.

---

## 3. Component Dependency Graph

This is the real dependency graph — not the SDLC phase order (intake→...→done), but *which subsystem must exist before which other subsystem can be built*. This graph is what determines implementation order (see `roadmap.md`), independent of how the finished product's runtime workflow looks.

```
                     ┌─────────────────────┐
                     │  Task Data Model     │  (§B.1 — foundational, everything reads/writes this)
                     └──────────┬───────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
 ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
 │ Cost/Sandbox/    │  │  LangGraph        │  │  Model Adapter   │
 │ TelemetrySink    │  │  Orchestration    │  │  Layer (§I)      │
 │ (§B.6,B.7,B.8)   │  │  Skeleton (§D)    │  │                  │
 └────────┬─────────┘  └─────────┬─────────┘  └────────┬─────────┘
          │                      │                     │
          └──────────┬───────────┴──────────┬──────────┘
                     ▼                      ▼
            ┌────────────────────┐  ┌──────────────────────┐
            │ Repository          │  │ Agent Base + MASC +   │
            │ Intelligence (§G)   │  │ Templates (§E.1, E.6) │
            │ MVP (Tree-sitter,   │  │                        │
            │ Zoekt, pgvector)    │  │                        │
            └─────────┬───────────┘  └───────────┬────────────┘
                      │                          │
                      ▼                          ▼
            ┌────────────────────────────────────────────┐
            │  Dynamic Requirements Engine (§E.4)          │
            │  — needs RI for auto-answer, needs Agent      │
            │    base + Confidence Model (§B.4) for exit    │
            └───────────────────┬───────────────────────────┘
                                │
                                ▼
            ┌────────────────────────────────────────────┐
            │  Real Agent Rosters, phase by phase (§E.8)   │
            │  Intake → Design → Implementation → QA →     │
            │  Release  (each phase's agents depend on the │
            │  previous phase's artifacts existing)        │
            └───────────────────┬───────────────────────────┘
                                │
                    ┌───────────┴────────────┐
                    ▼                        ▼
          ┌──────────────────┐    ┌────────────────────────┐
          │ HITL / Release    │   │  Minimal UI (§P)       │
          │ Governance (§D.7) │   │  — needs real agents + │
          │ — needs interrupt │   │    real HITL events to │
          │   skeleton + real │   │    render              │
          │   agent output    │   └────────────────────────┘
          └─────────┬──────────┘
                    ▼
          ┌──────────────────────────┐
          │  Workflow Policy Engine    │  (§F) — can only be
          │  (resolve_workflow_profile)│  correctly tuned once
          │                            │  real agent behavior
          │                            │  across risk tiers exists
          └─────────────┬──────────────┘
                        │
        ┌───────────────┼────────────────────┬───────────────────┐
        ▼               ▼                    ▼                   ▼
 ┌─────────────┐ ┌──────────────┐   ┌────────────────┐  ┌──────────────────┐
 │ RI at Scale  │ │ Context      │   │ Advanced QA     │  │ MCP Integrations  │
 │ (§G.4)       │ │ Engineering  │   │ (§K)            │  │ (§J)              │
 │              │ │ (§H)         │   │                 │  │                   │
 └──────┬───────┘ └──────┬───────┘   └────────┬─────────┘  └────────┬──────────┘
        └────────────────┴────────────────────┴───────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │ Evaluation Framework   │  (§L) — scores RunRecords
                        │                        │  from TelemetrySink + DB;
                        │                        │  never LangGraph types
                        └───────────┬─────────────┘
                                    ▼
                        ┌───────────────────────┐
                        │ Production Hardening   │  (§N) — proves every
                        │ (§N)                   │  mitigation against
                        │                        │  a system that fully exists
                        └───────────────────────┘
```

### 3.1 Independent Subsystems (No Cross-Dependency at Build Time)

These can be built in any relative order once their own prerequisites are met — useful to know because a solo engineer can pick whichever is more interesting/de-risking to build next without breaking the critical path:

- **Model Abstraction Layer (§I)** and **Repository Intelligence MVP (§G, minimal)** are mutually independent — both only depend on Phase 0 foundations.
- **UI (§P)** is independent of **Workflow Policy Engine (§F)** — the UI renders whatever state exists; it does not need routing logic to be sophisticated.
- **MCP Integrations (§J)** is independent of **Context Engineering (§H)** and **Repo Intelligence at Scale (§G.4)** — all three depend only on Phase 8 (real agents + HITL) or Phase 3 (RI proven), not on each other.
- **Advanced QA (§K)** is independent of **MCP Integrations (§J)**.

### 3.2 Hard Sequential Dependencies (Cannot Be Reordered)

- Orchestration (§D) cannot be built before the Task Data Model (§B.1) exists — the graph state is keyed to it.
- Agents (§E) cannot be built before the Model Abstraction Layer (§I) exists — every agent call goes through a `ModelAdapter`.
- The Dynamic Requirements Engine (§E.4) cannot be meaningfully built before Repository Intelligence MVP (§G) exists — its core value (auto-answer-from-repo) requires it.
- The Workflow Policy Engine's rules (§F.3) cannot be *correctly tuned* before real agents across at least Design, Implementation, and QA exist and have produced real pass/fail/confidence data to validate the rules against. A stub/default profile is used until then (see `roadmap.md` §"Fail-Closed defaults before Phase 10").
- Evaluation (§L) cannot produce meaningful KPIs before a population of real, varied task executions exists (Phases 5–14).
- Production Hardening (§N) chaos tests require the subsystems they're testing (Postgres HA, queue, model adapter swap) to already exist.

---

## 4. Runtime View: How a Task Actually Flows

This is the *finished-product* view (contrast with §3, which is the *build-order* view). Useful for understanding what each phase is incrementally building toward.

```
User/Ticket ──▶ Intake Subgraph ──▶ Requirements Subgraph ──▶ Design Subgraph
                                                                    │
                                                                    ▼
                                                          Implementation Subgraph
                                                          (Topology Selector → ExecutionPlan;
                                                           Wave Scheduler loops over waves;
                                                           per wave: Send → CodeGen × wave.width,
                                                           each branch: CodeGen → Validator(impl);
                                                           Fan-in Coordinator per wave: overlap +
                                                           WCP conflict → WaveHandoffNote;
                                                           Integration Validator after final wave)
                                                                    │
                                                                    ▼
                                                              QA Subgraph
                                                          (parallel QA tool runners)
                                                                    │
                                                                    ▼
                                                            Review Subgraph
                                                                    │
                                                                    ▼
                                                            Release Subgraph
                                                          (CI/CD-mediated deploy,
                                                           mandatory ApprovalGate)
                                                                    │
                                                                    ▼
                                                          Monitoring Subgraph
                                                     (incident ⇒ NEW Task via lineage,
                                                      never loops back into this graph)

Backward edges (§D.3) fire at any point above when a Validator, MASC check, or
Confidence floor breach demands it — always toward a named FeedbackReport (§D.8),
never a bare retry.

Repository Intelligence (§G) and Memory (§B.3) are NOT subgraphs — every box above
calls into them as a shared, long-lived service via tool calls.
```

### 4.1 Why Repository Intelligence Is a Service, Not a Subgraph

This is the single most important architectural decision to internalize before writing any orchestration code (§G.1). A LangGraph subgraph is scoped to one Task's lifetime. Repository Intelligence is a long-lived service independent of any Task: it indexes the **local working tree** (files on disk under `repo_root`, including uncommitted edits) via explicit `index` / `reindex`, is queried concurrently by many Tasks, and (at scale, §G.4) is federated across domain shards. Git activity is **not** the Phase 03 update trigger — see `docs/phases/phase-03/section-05.md` and `docs/decisions/2026-08-27-ri-working-tree-source-of-truth.md`. Modeling RI as a subgraph would mean either re-indexing per task (wasteful) or awkwardly smuggling a shared resource through task-scoped state (leaky). It is instead a standalone async service with its own lifecycle, exposed to every subgraph node through the single `RepositoryIntelligence` interface (§G.6). Agents never touch the graph DB or vector store directly — this is what keeps the retrieval backend swappable (NetworkX→Neo4j, pgvector→Qdrant) without touching agent code. After an agent writes files (Phase 05+), it must `reindex_paths` before the next RI read; retrieval fail-closes with `StaleIndexError` if the catalog lags the working tree.

### 4.2 Why the Workflow Policy Engine Is Deliberately Late

`resolve_workflow_profile()` (§F.3) is a pure, ordered, unit-testable rule function — but it can only be *validated* against real behavior once real agents exist across enough of the SDLC to observe how risk tier, confidence, and work type actually correlate with good outcomes. Building it early would mean guessing at rules with no data to check them against. The architecture handles this by using `WorkflowProfile.most_conservative()` (§F.1 — explicit field values, not an informal convention) everywhere until Phase 10 — every phase before that runs the standard/conservative path, not a shortcut path. This is why Phase 10 depends on Phases 5–9: it is a formalization and testing of routing logic that was implicitly "everything conservative" until then.

---

## 5. Agent Architecture Summary

Full detail in §E of the blueprint; summarized here for orientation.

- **Two reusable templates, not N bespoke classes**: `ApprovalGate` (human sign-off) and `Validator` (independent automated check). Every checkpoint and validation step in the entire system is a config-parametrized instance of one of these two templates. This is a deliberate anti-sprawl decision — resist the urge to special-case a new class per checkpoint.
- **One Manager per SDLC phase** coordinates that phase's sub-agents and is the graph's boundary node for that phase.
- **Sub-agents split only where tools/context genuinely differ** (e.g., Security QA needs different tools than Unit Test QA). Two agents processing different files in parallel is fan-out, not a specialization split.
- **MASC (§E.6)** is post-node middleware, not an agent — it runs after every agent node, cheapest-check-first (schema → confidence → semantic drift), before output is allowed into `SDLCState`.
- **Feedback Agent (§E.5)** is the named response to repeated failure — it does root-cause synthesis across failure history, not a blind retry. If its revised approach also fails, the system escalates to a human (Fail-Closed).
- **Intent Tracker (§E.7)** runs on every new user message (including HITL responses) to catch scope drift before it corrupts an in-flight implementation.

### 5.1 Communication Architecture Summary

Full detail in §D.9 / §D.4 / §D.10. **Workers never talk to workers.** Cross-worker knowledge is assembled only at Fan-in (per wave) via WCP → optional demotion/amendment → `WaveHandoffNote`.

- **Topology Selector / TP-01…TP-08 / Wave Scheduler** — **not LLM calls.** One Manager structured decompose; selector is Python in the same node (§D.10.11). Happy-path Implementation LLM count vs V3.0 is unchanged: 1 Manager + N CodeGen + 1 Integration Validator. TP-02 width gate is confidence `< 0.70`; §B.4 Implementation floor `0.75` is model-tier escalation — keep both. `WorkflowProfile.execution_order` is a hotfix/scheduling preference gate, not `ExecutionPlan.topology_class`.
- **Wave Scheduler** — sole mechanical `Send` issuer; Manager holds coordination authority only (§D.9.5).
- **WCP** — every worker exit report (`plan_version`, `wave_index`); input to Fan-in and handoff projection.
- **Fan-in** — per-wave boundary: overlap, semantic conflict, cross-wave check, merge (`merge_eligible`), demotion SM, amendment, handoff, advance.
- **Active plan ≠ history** — demotion rewrites remaining schedule and adds `demotion_ignore_keys`; append-only results are never rewritten.
- **`Validator(implementation)` (§D.4.0)** — runs per Send branch before Fan-in; tool-only static analysis. Failures route via FL-04 to the originating CodeGen sub-agent.
- **ClarificationEscalation protocol (§D.9.3)** — when a worker's assumptions break mid-task, it consults Repository Intelligence first, then stops its own branch and escalates (never guesses, never messages a peer). The Manager resolves the batch from design docs + RI; HITL is reached only for genuine requirement/scope/policy ambiguity.
- **ReplanContext (§B.2/§D.5)** — every replan (Feedback Agent, Fan-in-triggered, or otherwise) is handed structured history of prior attempts, so each attempt is strictly better-informed, never a blind re-run.
- **Explicitly rejected (§D.9.7):** worker↔worker messaging, swarm/debate/voting for core workflow, always-on coordination windows, recursive worker spawning, and an LLM-driven Merge Resolution Agent — merge conflicts are resolved by the Fan-in **wave demotion** state machine (§D.4.4), never by a merge agent or extra model call.
- **Idempotent workers (§D.9.8):** every parallel worker must tolerate retries, checkpoint replay, and resume without duplicate side effects.
- **Pre-dispatch overlap (§D.4.2):** superseded by Topology Selector + Fan-in. The Manager does not `Send` and does not run a second overlap LLM. File overlap becomes blocking SDG edges or Fan-in demotion.
- **Merge eligibility:** `merge_eligible` = `status==validated` and attempt not in `demotion_ignore_keys`. Results are append-only; demotion never rewrites status.
- **`AgentEvent` observational only (§B.8, §P):** never used for routing, scheduling, planning, or replanning. Not an evaluation scoring source.
- **Telemetry is orchestrator-independent (§B.8):** LangGraph talks to `TelemetrySink` via `telemetry_adapter.py`. Evaluators consume `RunRecord`, not graph nodes.
- **Task ↔ graph sync (§D.2.1):** `Task.state` in Postgres is the durable phase source of truth; updated on graph node entry. `SDLCState` does not carry `task_state`.
- **HITL lifecycle (§D.7.1):** `hitl_log` (Postgres) is durable; `SDLCState.hitl_queue` is in-graph pending set; UI queries `hitl_log WHERE responded_at IS NULL`.
- **Git isolation (§D.4.3):** one worktree per `(task_id, subtask_id)`; Fan-in merges into integration worktree only.

---

## 6. Memory Architecture Summary

Four physical tiers (§B.3), mapped to named scopes:

| Tier | What Lives Here | Where |
|---|---|---|
| Working | Active `SDLCState`, agent scratch reasoning | LangGraph state + Postgres checkpoint |
| Episodic | Completed task transcripts, outcomes, regression history | Postgres + pgvector |
| Semantic | Repo knowledge graph, architecture summaries, ADRs | Graph DB + Zoekt + pgvector (via RI service) |
| Procedural | Distilled playbooks, versioned policy rules | Versioned YAML/JSON, human-reviewed |

**The one rule that prevents this from becoming an unbounded-context system:** LangGraph state holds *only* Working memory. Everything else is retrieval-on-demand via tool call, never force-injected. Phase transitions carry a **Phase Handoff Packet** (§B.5, hard token cap per transition) — not the full upstream artifact.

---

## 7. Safety Model Summary

Three axioms carried through every part of the system, restated here because they justify implementation-order decisions elsewhere in this doc set:

1. **Fail-Closed by Default (Principle 8, §A.2).** Any scoring/policy/validation mechanism that errors, times out, or returns malformed output routes toward *more* human oversight, never more autonomy. This is why confidence-scorer failures don't default to "assume fine" — they default to "block."
2. **Irreversible actions always require human approval regardless of confidence (Principle 4).** Confidence tunes *speed of routing*, never *whether* a production deploy needs a human.
3. **Deterministic and auditable over clever (Principle 5).** Rule tables and named tools beat learned/black-box equivalents wherever both are viable — this is why routing is an ordered `if/elif` function (§F.3), not a trained classifier.
4. **Intentional worker isolation (Principle 9, §A.2).** Parallel workers are deliberately unaware of sibling workers; cross-worker knowledge is delayed until Fan-in. This preserves determinism, auditability, reproducibility, and deadlock-free parallelism — not merely a messaging restriction.
5. **`AgentEvent` is observational only (§B.8, §P).** Routing, scheduling, planning, and replanning never read the event stream; control flow uses `SDLCState` typed channels, Validators, RI, and the Workflow Policy Engine only.
6. **Telemetry never fails a task (§B.8).** Exporter down → log and continue. Evaluation never imports LangGraph.

---

## 8. What This Means for Implementation Order

The single sentence that should guide every phase-ordering decision in `roadmap.md`:

> **Build the boring, deterministic safety scaffolding first (Task model, sandbox, cost control, tracing, checkpointing, model adapter) — because every subsequent phase is an agent or a policy layered on top of it, and agents are the hardest thing in this system to safely retrofit safety controls onto after the fact.**

See `roadmap.md` for the full phase-by-phase plan and `development_strategy.md` for the per-task engineering lifecycle used inside every phase.
