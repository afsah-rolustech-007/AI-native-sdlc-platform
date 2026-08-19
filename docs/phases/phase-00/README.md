# Phase 00 — Foundations

## Goal

Build the safety scaffolding the entire platform depends on, before a single agent exists. At the end of this phase, a "dummy task" can flow through intake → sandbox execution → structured trace log → budget-tracked completion, with a full audit trail in Postgres — with zero LLM calls involved.

## Why This Phase Exists

Every later phase adds an agent, a policy, or a UI on top of this one. Retrofitting cost control, sandboxing, or tracing after agents already exist means auditing every agent's code path for compliance — expensive and error-prone. Building it first means every agent from Phase 05 onward is *born* compliant, because the interfaces it must use (sandbox, budget tracker, tracer) are the only way to do the things agents need to do.

This phase corresponds to `final_plan.md` Part C, Phase 0, and touches §B.1 (Task Data Model), §B.6 (Security Model / sandboxing), §B.7 (Cost Governance), §B.8 (Observability).

## Dependencies

None. This is the root of the dependency graph (see `architecture.md` §3).

## High-Level Architecture

```
┌────────────────────┐     ┌──────────────────────┐     ┌────────────────────┐
│   Task (Pydantic)    │────▶│  Postgres persistence │     │  OTel trace exporter│
│   §B.1               │     │  (tasks, cost_tracking│     │  (console/OTLP)      │
└────────────────────┘     │   tables)             │     └────────────────────┘
                            └──────────────────────┘               ▲
                                                                     │
┌────────────────────┐     ┌──────────────────────┐                │
│  Kill-switch node    │────▶│  Ephemeral, network-  │────────────────┘
│  (budget enforcement)│     │  restricted sandbox   │  every sandbox run emits
└────────────────────┘     │  (per-task container) │  a structured trace event
                            └──────────────────────┘
                                       ▲
                            ┌──────────┴───────────┐
                            │ Redis-backed job queue │
                            │ (ARQ) — scaffolding    │
                            │ only, no real jobs yet │
                            └───────────────────────┘
```

Nothing here is LangGraph or LLM-aware yet — that's Phases 01 and 02. This phase's job is to make "run something for a task, safely, cheaply, and observably" a solved, tested problem.

## Expected Live Demo

A single CLI script, `scripts/demo_phase0.py`, that:
1. Constructs a `Task` (work_type=`feature`, risk_tier=`low`).
2. Persists it to Postgres.
3. Enqueues a trivial "job" (e.g., `echo hello && sleep 1`) that runs inside the sandbox.
4. The kill-switch tracks token/cost budget consumption for the (simulated) job.
5. Prints the OTel trace event and the final `cost_tracking` row read back from Postgres.

Running this script twice — once within budget, once forcing a budget breach — should visibly produce two different terminal states (`done` vs. `blocked`, force-routed by the kill-switch).

## Deliverables

- `packages/common/task.py` — full Task data model (§B.1).
- `db/migrations/` — initial Alembic schema for `tasks`, `cost_tracking`, `hitl_log` (unused until Phase 8, but schema created now per §R) tables.
- `packages/common/sandbox.py` — ephemeral container execution wrapper.
- `packages/common/budget.py` — kill-switch node logic.
- `packages/common/telemetry.py` — `TelemetrySink` Protocol (§B.8).
- `packages/common/tracing.py` — `OtelTelemetrySink` + `emit_node_event` helper.
- `apps/worker/` — ARQ worker entrypoint (no real jobs yet, just the runtime).
- CI pipeline running lint/type/unit tests on every push.

## Sections

1. [Task Data Model & Persistence](section-01.md)
2. [Database Schema, Migrations & Config Management](section-02.md)
3. [Cost Kill-Switch & Budget Governance](section-03.md)
4. [Execution Sandbox](section-04.md)
5. [TelemetrySink & OTel Adapter](section-05.md)
6. [Job Queue Scaffolding & CI Pipeline](section-06.md)
