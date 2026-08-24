# Phase 06 — Design & Implementation Agents

## Goal

The platform's largest and most consequential phase: real, design-driven code generation. By the end of this phase, an approved `RequirementsSpec` flows through a real architecture/design step, into a decomposed task plan, into parallel code-generation sub-agents, through conflict detection and integration validation, producing an actual diff against a real repository — with the Feedback Agent handling repeated failure and MASC's semantic-drift check finally active.

## Why This Phase Exists

This is where the platform starts doing the thing it exists to do. Every prior phase (00–05) built the scaffolding to make this phase safe and observable; every phase after this (07+) adds QA, governance, scale, and measurement *around* what this phase produces. It is sequenced here — after Planning & Intake are proven (Phase 05) — because Design and Implementation agents are meaningfully harder to get right (multi-agent coordination, parallel fan-out, conflict resolution) and benefit from a already-proven agent/template/MASC pattern to build on rather than inventing it here too.

## Dependencies

Phase 05 (real agents, templates, MASC, real approved requirements to design against).

## High-Level Architecture

```
Approved RequirementsSpec
        │
        ▼
  Design Manager  ──(if touches_shared_infra or security-sensitive)──▶ Security Architect
        │                                                                      │
        ▼                                                                      │
  Repo Architecture Analyst (grounds design in real repo structure)            │
        │◀─────────────────────────────────────────────────────────────────────┘
        ▼
  Reflection pass (§M.3) ──▶ Validator(design) ──fail──▶ FL-02 (back to Design Manager, 5x)
        │                                        └─fail──▶ FL-03 (requirement gap → Requirements, HITL)
        ▼ pass
  ApprovalGate(design)
        │
        ▼
  Implementation Manager ── decomposes into TaskDecomposition
        │
        ▼
  Topology Selector (§D.10.3) ── deterministic, no LLM ── produces ExecutionPlan + TopologyDecisionRecord
        │                      (topology_class = parallel | sequential | hybrid)
        ▼
  Wave Scheduler (§D.4.0) ── loops over ExecutionPlan.waves
        │
        │  per wave:
        │    [Send API fan-out] ──▶ CodeGen Sub-agent × wave.width
        │          │                      │
        │          │                each branch: diff + WCP (§D.9.2)
        │          │                      │
        │          │                Validator(implementation) [per-branch, tool-only, §D.4.0]
        │          │                      │
        │          │                fail ──▶ FL-04 (CodeGen, 3x) ──▶ Feedback Agent ──▶ HITL
        │          │                blocked branch ──▶ ClarificationEscalation (§D.9.3) and stops
        │          ▼
        │    Fan-in Coordinator (deterministic, §D.4.1) — intra-wave file overlap + WCP semantic conflict
        │          │    overlapping/conflicting? → Wave Demotion (§D.4.4): new serial wave, plan amendment
        │          │    needs_manager_attention / open escalations? → batched Manager replan
        │          │    all clean? → assemble WaveHandoffNote (§D.10.6) for next wave
        │          ▼
        │    (if more waves remain: loop back to Wave Scheduler with WaveHandoffNote)
        │
        ▼  (final wave closed)
  Integration Validator ──fail──▶ FL-05 (Implementation Manager, re-assign, 2x)
        │
        ▼
  [QA phase — still a stub until Phase 07]
```

**PARALLEL, SEQUENTIAL, and HYBRID are not three code paths — they are three shapes of the same `ExecutionPlan`.** A PARALLEL plan is one wave of width N; a SEQUENTIAL plan is N waves of width 1; a HYBRID plan is the general DAG case. The Wave Scheduler handles all three identically. `topology_class` is a telemetry label derived after the plan is built, never a control switch (§D.10.1).

**Communication invariant (§D.9.1 / Principle 9, §A.2), binding from this phase onward:** CodeGen sub-agents never communicate with each other, directly or indirectly. Workers remain intentionally unaware of siblings; cross-wave knowledge is assembled only at Fan-in via `WaveHandoffNote`. All coordination flows through the Implementation Manager, the Fan-in Coordinator, `SDLCState`, the Blackboard, or Repository Intelligence. Workers must also be idempotent (§D.9.8) — safe under retry, resume, and checkpoint replay.

## Expected Live Demo

Submit a moderately complex feature request (touching 2–3 files with a real interface dependency between them) through the full pipeline from Phase 05's requirements approval into Design, then Implementation. Show: the Design Manager's architecture output and its reflection-pass self-critique; `Validator`(design) passing; `ApprovalGate`(design) approval; the Implementation Manager's WHAT-only decomposition; Topology Selector `ExecutionPlan`; Wave Scheduler `Send` of 2+ CodeGen workers; a deliberately-induced file-overlap conflict triggering **wave demotion** (active plan rewritten, ignore-keys set); Integration Validator once after the last wave; a final real diff against the demo repository.

## Deliverables

- `packages/agents/design/design_manager.py`, `repo_architecture_analyst.py`, `security_architect.py`.
- `packages/agents/implementation/implementation_manager.py`, `codegen_agent.py`, `feedback_agent.py`.
- `packages/orchestration/topology_selector.py` — `plan_execution_waves()` (§D.10.3).
- `packages/orchestration/wave_scheduler.py` — sole CodeGen `Send` issuer (§D.9.5).
- `packages/orchestration/fan_in_coordinator.py` — per-wave boundary + demotion SM (§D.4.1, §D.4.4).
- `packages/orchestration/blackboard.py` — minimal `BlackboardService`.
- Schemas: `ExecutionPlan`, `WaveHandoffNote`, WCP `plan_version`/`wave_index`, `demotion_ignore_keys`.
- MASC Check 3 activated; `FL-02`–`FL-05` operational.

## Sections

1. [Design Manager & Repo Architecture Analyst](section-01.md)
2. [Security Architect & Reflection Pass](section-02.md)
3. [Validator(design), ApprovalGate(design) & Design Feedback Loops](section-03.md)
4. [Implementation Manager, Topology Selector & Blackboard](section-04.md)
5. [CodeGen Workers, Wave Scheduler & Send Dispatch](section-05.md)
6. [Fan-In (Wave Boundary), Demotion, Escalation & Integration Validator](section-06.md)
7. [Validator(implementation) & Feedback Agent](section-07.md)
