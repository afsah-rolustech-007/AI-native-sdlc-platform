# Phase 01 — Orchestration Skeleton

## Goal

A working LangGraph `StateGraph`, keyed to a `Task`, with durable PostgreSQL checkpointing and a proven interrupt/resume round-trip — with dummy/no-op nodes standing in for every SDLC phase. By the end of this phase, a task can be paused for "approval," the entire process can be killed, and the task resumes correctly from its last checkpoint.

## Why This Phase Exists

This is the mechanical backbone every agent (Phase 05+) will run inside. The two hardest things to retrofit later are durability (what happens on crash) and human-in-the-loop interrupt semantics — both are core LangGraph features, but wiring them correctly (Postgres checkpointer, `thread_id` handling, `interrupt()`/`Command(resume=...)`) needs to be proven with trivial nodes before real agent logic adds complexity on top. Corresponds to `final_plan.md` §D (LangGraph System Architecture) at skeleton level, and the interrupt mechanics of §D.7.

## Dependencies

Phase 00 (Task model for `thread_id` keying; `TelemetrySink` for phase spans; sandbox unused yet but budget tracker will wrap nodes here).

## High-Level Architecture

```
Task ──▶ Orchestrator StateGraph (per task, thread_id = task.id[:255])
           │
           ├── intake_node (no-op stub)
           ├── requirements_node (no-op stub)
           ├── design_node (no-op stub) ── interrupt() here for demo purposes
           ├── implementation_node (no-op stub)
           ├── qa_node (no-op stub)
           ├── review_node (no-op stub)
           ├── release_node (no-op stub)
           └── monitoring_node (no-op stub)
                    │
                    ▼
          AsyncPostgresSaver (checkpoint after every node)
```

Every node is a placeholder that updates `Task.state` via `update_task_state()` on node entry (§D.2.1) — no LLM, no real logic. The point of this phase is proving the *mechanism*, not the *content*.

## Expected Live Demo

Run a task through the skeleton graph until it hits the `design_node`'s `interrupt()`. Kill the worker process (`kill -9`). Restart the worker. Issue a `Command(resume=...)` for that task's `thread_id` and confirm it resumes exactly where it left off — not from the beginning. Repeat this crash-and-resume test 20 times in a loop with randomized kill timing; log the success rate.

## Deliverables

- `packages/orchestration/state.py` — `SDLCState` TypedDict with all reducers, per §B.2 (even though most fields are unused by stub nodes at this phase).
- `packages/orchestration/checkpointers/postgres.py` — `AsyncPostgresSaver` wiring with `thread_id[:255]` enforcement.
- `packages/orchestration/telemetry_adapter.py` — LangGraph node wrap → `TelemetrySink` only (§B.8.5).
- Parent `StateGraph` with 8 stub nodes matching the phase state machine (§D.3).
- One `interrupt()`/`Command(resume=...)` round-trip proven working.
- Crash-recovery test harness (20-trial loop).

## Sections

1. [SDLCState Schema & Stub Graph Topology](section-01.md)
2. [PostgreSQL Checkpointer & thread_id Handling](section-02.md)
3. [Interrupt / Resume Round-Trip](section-03.md)
4. [Crash Recovery Test Harness](section-04.md)
