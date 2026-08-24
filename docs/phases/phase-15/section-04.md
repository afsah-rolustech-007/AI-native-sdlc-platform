# Section 04 — RunRecord, EvaluationEngine & MVP Evaluators

## Objective

Implement the evaluation *contracts* in §L.6: `RunRecord`, `Evaluator`, `EvaluationEngine`, `Score`, `Evidence`. MVP evaluators are deterministic only (task success, cost, cycle time, HITL, rollback, retry/validation fail rates, WCP schema-complete, MASC pass/fail, Fan-in silent-merge forbidden). No LLM-as-Judge.

## Why It Exists

Section 01's pipeline must not become a bag of SQL snippets. Phase 15 CI (Section 05) and golden replay (Section 02) need one `evaluate(run)` entry point that is ignorant of LangGraph.

## Expected Architecture

`packages/evaluation/engine.py`: `evaluate(run: RunRecord, case: EvaluationCase | None) -> EvaluationResult`.

`packages/evaluation/trajectory.py`: helpers to attach span export refs if present; reconstruction of Decision→Action→Result is storage only at MVP (no trajectory *score*).

`packages/evaluation/evaluators/`: one module per metric group (`system.py`, `communication.py`, `validation.py`). Each implements `Evaluator`.

WCP completeness: MASC Check 1 already validated schema at write time — evaluator confirms a WCP row exists per validated `ImplementationResult` (when those lists are in the hydrated run). Missing WCP → score 0 for `comm.wcp_schema_complete`.

## Dependencies

Section 01 (pipeline persist path). Phase 00 telemetry + Phase 06 WCP fields in state snapshots if the loader can read the last checkpoint via Postgres checkpointer **without** importing LangGraph graph code — use SQL/JSON of checkpoint table or a thin `packages/evaluation/loaders/postgres.py` that reads documented columns only. If checkpoint JSON is too coupled, score from `feedback_loop_events` / `cost_tracking` / `hitl_log` only in MVP and treat WCP metrics as Phase 2.

**MVP fallback (document in code comments):** if checkpoint payload cannot be read without LangGraph types, skip WCP evaluator and record `metric_id=comm.wcp_schema_complete` as `skipped` (do not fail the job). Add the loader path once a stable export exists.

## Atomic Implementation Tasks

1. TypedDicts from §L.6.1 in `packages/evaluation/types.py`.
2. `EvaluationEngine` dispatching a registry of evaluators.
3. Deterministic MVP evaluators listed in §L.7 where data exists.
4. Unit tests with a fake `RunRecord` (no live graph): expected scores for success vs blocked, cost, HITL count.
5. Grep: no `langgraph`, no `opentelemetry` in `packages/evaluation/`.

## Manual Testing Procedure

Score a completed demo task through `EvaluationEngine` in a REPL; print `scores`.

## Expected Demo

Printed scorecard: `system.task_success`, `system.cost_usd`, `system.hitl_count`, `system.cycle_time_s`.

## Acceptance Criteria

- [ ] Engine returns `list[Score]` with evidence pointers (table names / task_id, not raw prompts).
- [ ] LLM-as-Judge is not called.
- [ ] Package import graph excludes LangGraph.

## Risks

Checkpoint coupling — use the documented fallback rather than leaking orchestrator types.

## Future Improvements

Phase 2 evaluators in §L.7 (scope adherence, repeated tools). LLM-judge behind the same Protocol — Advanced.

### Topology Evaluation Metrics (Phase 2 — gated on Phase 06 wave data)

Once Phase 06 is deployed and `TopologyDecisionRecord` rows exist, add `packages/evaluation/evaluators/topology.py`:

| `metric_id` | What it measures | Source |
|---|---|---|
| `topology.class` | sequential / parallel / hybrid | `TopologyDecisionRecord.topology_class` (§D.10.3 derivation) |
| `topology.rules_fired` | TP hard/soft ids | `policy_rules_fired` |
| `topology.wave_count` / `widths` | Planned shape | record fields |
| `topology.plan_amended` / `amendment_rate` | `plan_amendment_count` | state / events |
| `topology.wave_demotion_rate` | `wave_demotion` events | TelemetrySink |
| `topology.unnecessary_serialization` | sequential + zero conflicts + RI available | derived |
| `topology.unnecessary_parallelism` | parallel/hybrid + demotion>0 | derived |
| `topology.ri_coverage` | RI-verified vs advisory edges | SDG |
| `topology.happy_path_llm_budget` | Implementation `llm_call` count == 1+N+1 | TelemetrySink; no model_id on selector/scheduler/fan-in |

Pure Python against the read model — no LangGraph imports.
