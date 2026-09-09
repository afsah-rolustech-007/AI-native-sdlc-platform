# Phase 04 — Dynamic Requirements Engine

## Goal

Build the Dynamic Questioning Engine (§E.4) as a **standalone, testable package** that takes a raw engineering request plus a repository and produces a `RequirementsSpec` plus an auditable trace of what was known, inferred, auto-answered from the repository, asked of the engineer, left unresolved, and why questioning stopped.

LangGraph wiring is **Phase 05**. This phase must be independently testable with a CLI harness.

## Why This Phase Exists

The blueprint calls requirements "the platform's most important phase and historically its most under-specified component." Building the engine as a package — not yet a graph node — lets it be tested against dozens of synthetic scenarios without running a full agent graph.

It is buildable now because it depends on Repository Intelligence (Phase 03) for auto-answer-from-repo. It is **not** a vibe-coding interviewer and **not** a naive:

`request → question → search repo → answer → question → search repo → …`

loop. That loop is expensive, over-asks engineers, and can lock in wrong auto-answers. The engine is **evidence-first**: establish what the request and the repository already make cheap and deterministic, then ask only what remains a human decision.

## Dependencies

Phase 03 (`RepositoryIntelligence` — four unfused signals, architecture summary, freshness). Phase 02 (`ModelAdapter`) for one structured extraction call. Phase 00 (config loading, telemetry).

## High-Level Architecture

```
Raw request
    │
    │  1 LLM structured call (request only — repo-blind)
    ▼
 ClaimSet
    │
    │  once per session, cached on catalog_hash
    ▼
 SessionRepoSnapshot  ←  RI: index_status + capped architecture_summary
                         + capped repo map + bounded manifest facts
    │
    ▼
 Classify claims     FACT | INFERENCE | DECISION | UNKNOWN | CONTRADICTION
    │
    ▼
 Activate question slots (YAML bank, applies_if, depends_on DAG)
    │
    ▼
 EvidencePlan per slot → progressive targeted RI (budgeted, cached)
    │
    ▼
 Auto-answer (deterministic extractors)  or  rank remaining human questions
    │
    ▼
 Engineer question (templates + evidence)  →  updated claims
    │
    ▼
 RequirementsSufficiency (3-way exit)  →  RequirementsSpec (§B.2 projection)
```

Nothing here touches LangGraph. The engine is importable. Human answers in this phase come from the CLI; Phase 05 replaces that with `interrupt()`.

Workers still do not talk to workers. The engine talks to `RepositoryIntelligence` and `ModelAdapter` as shared services, and records results onto its own session objects. Phase 05 is what copies the finished `RequirementsSpec` into `SDLCState`.

## What to reuse from Phase 03 (do not rebuild)

| Phase 03 already provides | Phase 04 does with it |
|---|---|
| `get_architecture_summary()` — deterministic AST JSON, **never LLM** | Call **once** per session; **cap** fields; cache on `catalog_hash` |
| `get_aider_repo_map(top_n)` — in-degree placeholder (PageRank is Phase 12) | Call once; `top_n=20` |
| `index_status()` — `catalog_hash`, freshness, `file_count` | Cache key + stale/unindexed fail-closed |
| `get_file_structure` / `get_symbol_*` | EvidencePlan when the identifier is known |
| `search_codebase` (Zoekt) | EvidencePlan for known tokens; skip-not-empty on `ZoektUnavailableError` |
| `get_callers` / `get_dependents` / `get_impact_set` | EvidencePlan for blast radius / existing callers |
| `search_concepts` (pgvector) | **Last resort**, `top_k=3`, `paths`/`kinds`/`min_score`; never FACT |
| Four signals kept separate; `find_relevant_context` raises | **Do not fuse.** Do not call the stub. |

Phase 03 `tech_stack` is **language from file suffix** (`python`, `typescript`), not a framework. The snapshot must not claim "this is a FastAPI project" from the summary alone.

## USE NOW vs DEFER

### USE NOW

- One structured LLM extraction (`ClaimSet`) from the raw request
- Evidence-first reasoning (classify before asking)
- Session repository snapshot (cached Phase 03 metadata + bounded manifests)
- Progressive **targeted** retrieval driven by `EvidencePlan`, not a global 0–5 pipeline
- Claim classification: FACT / INFERENCE / DECISION / UNKNOWN / CONTRADICTION
- Simple information-value ranking (additive heuristic + mandatory gate)
- Deterministic `RequirementsSufficiency` 3-way exit
- Exact `compute_confidence()` (§B.4) as a **platform function** that **fail-closes** on missing signals — not used as the Phase 04 loop exit with fake inputs
- Visible auto-answer + evidence in the session trace (Screen 2 later)

### DEFER

- LLM-as-a-Judge for evidence support/contradiction
- BED-LLM / conformal information pursuit
- Learned retrieval router / Adaptive-RAG classifier
- RRF / `find_relevant_context` (Phase 12)
- LangGraph `interrupt()`, Intent Tracker, `Validator`(requirements) (Phase 05)
- Episodic `precedent_strength` (Phase 06+)
- Personalized PageRank repo map (Phase 12)
- Framework detection inside RI itself (catalog is `.py`/`.ts`/`.tsx` only)

## Expected Live Demo

CLI against three fixtures (reuse the Phase 03 benchmark corpus where possible):

1. **Well-specified feature** on a repo that already has auth — most stack/API slots auto-answer from snapshot + lexical; 0–2 human questions; exit via sufficiency.
2. **Vague one-liner** — extract yields UNKNOWNs; ranking asks a small set of high-value questions, not the whole bank.
3. **Security-sensitive request** (auth/PII) — `Qsec1–3` activate and are asked unless the engineer already stated them; repository JWT facts do **not** silently become the user's compliance decision.

Print the full claim/evidence/question/auto-answer trace and the projected `RequirementsSpec`.

## Deliverables

- `packages/requirements_engine/` — engine, models, snapshot, retrieval, ranking, sufficiency, spec projection.
- `packages/common/confidence.py` — §B.4 formula, fail-closed, unit-tested; **no placeholders imputed**.
- `configs/question_bank/` — versioned YAML slots with `applies_if`, `depends_on`, `evidence_plan`.
- CLI harness + fixtures for the three demo scenarios.
- Benchmark: LLM/RI call counts, auto-answer correctness, human-question count (not retrieval fusion).

## Sections

1. [ClaimSet, Evidence, and Spec Projection](section-01.md)
2. [Question Bank, DAG, and Predicate Engine](section-02.md)
3. [Session Repository Snapshot](section-03.md)
4. [EvidencePlan and Progressive Retrieval](section-04.md)
5. [Classification, Auto-Answer, and Question Ranking](section-05.md)
6. [Sufficiency Gate, B.4 Function, CLI, and Benchmarks](section-06.md)

## Implementation plan (files)

No file > 500 lines. LangGraph stays out.

| Path | Role |
|---|---|
| `packages/requirements_engine/models.py` | Shared enums, `Question`, `AutoAnswer`, session events |
| `packages/requirements_engine/claims.py` | `Claim`, `ClaimSet`, `Provenance`, epistemic status |
| `packages/requirements_engine/extract.py` | One `ModelAdapter` structured extract (repo-blind) |
| `packages/requirements_engine/context.py` | Phase-04 `WorkflowContext` subset (`None` = unknown) |
| `packages/requirements_engine/question_bank.py` | YAML load, referential integrity, cycle detection |
| `packages/requirements_engine/dag.py` | Slot activation, topo order, re-eval after answers |
| `packages/requirements_engine/snapshot.py` | Session cache around RI summary/status/map |
| `packages/requirements_engine/manifests.py` | Bounded allowlist read of dependency files |
| `packages/requirements_engine/plans.py` | `EvidencePlan` parse + per-need method order |
| `packages/requirements_engine/retrieve.py` | Targeted RI + in-session query cache |
| `packages/requirements_engine/classify.py` | Deterministic epistemic status |
| `packages/requirements_engine/auto_answer.py` | Typed extractors; never semantic → FACT |
| `packages/requirements_engine/rank.py` | Additive heuristic + mandatory gate |
| `packages/requirements_engine/render.py` | Template questions grounded in evidence (no LLM) |
| `packages/requirements_engine/sufficiency.py` | 3-way exit |
| `packages/requirements_engine/project.py` | `ClaimSet` → §B.2 `RequirementsSpec` |
| `packages/requirements_engine/engine.py` | Orchestrator (`step` / `run`) |
| `packages/requirements_engine/trace.py` | Append-only session log for Screen 2 / Phase 15 |
| `packages/common/confidence.py` | `compute_confidence()` only |
| `configs/question_bank/*.yaml` | Policy |
| `scripts/demo_requirements_engine.py` | CLI demo |
| `tests/unit/test_*.py` / `tests/integration/test_requirements_*.py` | Coverage below |
| `tests/contract/test_repo_intel_boundary.py` | Add `packages/requirements_engine` to caller trees |

Do **not** add RI methods, RRF, or a second architecture-summary generator.
