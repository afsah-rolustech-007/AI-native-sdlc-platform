# Section 05 — CodeGen Workers, Wave Scheduler & Send Dispatch

## Objective

Implement CodeGen workers and the **Wave Scheduler** (§D.4.0 / §D.4.0.1 / §D.9.5): the sole graph node allowed to return LangGraph `Send` for CodeGen. PARALLEL / SEQUENTIAL / HYBRID are plan shapes only — one scheduler loop.

## Why It Exists

LangGraph needs a static compiled graph with dynamic `Send` fan-out. The Scheduler reads the active `ExecutionPlan`, dispatches one wave, waits for Fan-in, then re-enters or exits to Integration Validator.

## Expected Architecture

### Wave Scheduler (`packages/orchestration/wave_scheduler.py`)

- Reads `current_wave_index`, `execution_plan`.
- Returns `[Send(codegen_branch, payload)…]` for ids in `waves[current_wave_index]` (honour `dispatch_concurrency ≤ width`).
- Payload includes subtask spec + current `WaveHandoffNote` (if any) + plan_version/wave_index.
- After Fan-in advances index: `Command(goto=wave_scheduler)` or route to Integration Validator when done.
- **Not an LLM. Not a Worker.** Holds mechanical dispatch privilege only (§D.9.5).
- `compact_at_wave_close`: **no-op in Phase 06**; Phase 12 wires T2/T3. Must not change topology.

### CodeGen

`CodeGenAgent` — progressive RI tools (§H.4); isolated worktree (§D.4.3); emits diff + WCP (`plan_version`, `wave_index`); ClarificationEscalation path; idempotent under `(task_id, subtask_id, plan_version, attempt_number)`.

Per-branch: `CodeGen → Validator(implementation)` before Fan-in (§D.4.0).

Base commit: wave 0 → `task_base_sha`; later waves / demotion redispatches → integration HEAD at dispatch time.

## Dependencies

Section 04 (`ExecutionPlan`), Phase 00 sandbox, Phase 03 RI tools.

## Atomic Implementation Tasks

1. WaveSchedulerNode with Send + loop + termination.
2. CodeGen tool loop + WCP schema fields including plan_version/wave_index.
3. Git isolation contract §D.4.3.
4. Tests: sequential plan; parallel plan; hybrid plan; idempotent replay; Scheduler refuses ids not in active wave; no Send from CodeGen.

## Acceptance Criteria

- [ ] Only Wave Scheduler returns CodeGen `Send`.
- [ ] Width-1 waves use the same code path as wide waves.
- [ ] Next wave sees integration HEAD + WaveHandoffNote, not raw sibling diffs.
- [ ] Idempotency keys include `plan_version`.

## Risks

- Recursion limit vs wave height — set per §D.4.0.1.
- Checkpoint growth — Blackboard pointers only in state.
