# Implementation Roadmap

This is the master index. It converts `final_plan.md` Part C (the blueprint's own dependency-ordered phase table) into a solo-engineer-executable plan: 17 phases (0–16), each with a `phases/phase-NN/README.md` and a set of focused sections. Read `architecture.md` first for *why* things depend on each other, and `development_strategy.md` for *how* each section gets built. This document is the *what, in what order*.

---

## 1. Phase Index

| Phase | Name | Sections | Hard Dependencies | One-Line Objective |
|---|---|---|---|---|
| [00](phases/phase-00/README.md) | Foundations | 6 | None | Safety scaffolding before any agent writes code. |
| [01](phases/phase-01/README.md) | Orchestration Skeleton | 4 | 00 | A durable, resumable LangGraph graph with a working interrupt/resume round-trip. |
| [02](phases/phase-02/README.md) | Model Abstraction Layer | 4 | 00 | Model-independence structural from day one. |
| [03](phases/phase-03/README.md) | Minimal Repository Intelligence | 6 | 00, 02 | Working retrieval at small scale before scaling. |
| [04](phases/phase-04/README.md) | Dynamic Requirements Engine | 4 | 03 | Adaptive clarification loop, not a checklist. |
| [05](phases/phase-05/README.md) | Planning & Intake Agents | 6 | 01, 02, 04 | Wire the Questioning Engine into a real, running intake graph. |
| [06](phases/phase-06/README.md) | Design & Implementation Agents | 7 | 05 | Design-driven, validated code generation with parallel fan-out. |
| [07](phases/phase-07/README.md) | Core QA Agents | 5 | 06 | Incremental, impact-scoped QA and bug validation. |
| [08](phases/phase-08/README.md) | HITL & Release Governance | 5 | 01, 07 | Real approval gates and a real PR flow — nothing merges without them. |
| [09](phases/phase-09/README.md) | Minimal UI | 6 | 08 | Make the whole system legible to a human. |
| [10](phases/phase-10/README.md) | Workflow Policy Engine | 4 | 05, 06, 07, 08, 09 | Replace "always conservative" with real, tested routing logic. |
| [11](phases/phase-11/README.md) | Repository Intelligence at Scale | 5 | 03 (proven) | 100k–1M+ file federated retrieval. |
| [12](phases/phase-12/README.md) | Context Engineering | 5 | 11 | Token efficiency without accuracy loss. |
| [13](phases/phase-13/README.md) | Advanced QA | 5 | 07, 10 | Full QA capability stack (security, mutation, performance, a11y). |
| [14](phases/phase-14/README.md) | MCP & External Integrations | 5 | 08 | Connect to the real engineering ecosystem (GitHub, Jira, Slack). |
| [15](phases/phase-15/README.md) | Evaluation Framework | 5 | 05–14 | Measure real behavior, not assumed behavior. |
| [16](phases/phase-16/README.md) | Production Hardening | 0 (single README) | All prior | Prove every mitigation works, not just that it's designed. |

**Total: 17 phases.** Phases 00–15 are broken into sections (each following the fixed template described in `phases/phase-00/README.md`'s sibling sections). Phase 16 is a single, section-free hardening README, since it audits and verifies existing components rather than building new ones.

---

## 2. Dependency Analysis

### 2.1 Critical Path (Cannot Be Parallelized by a Solo Engineer, Must Be Built in This Order)

```
00 → 01 ─┐
00 → 02 ─┼─→ 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 ─┬─→ 13
         │                                            ├─→ 14
         │                                            ├─→ 15
         │                                            └─→ (11, 12 feed in below)
                                    03 (proven) → 11 → 12 ──┘
                                                             → 16 (needs everything)
```

Read this as: Phases 00–10 are a strict single-file line — each genuinely cannot start before the previous one produces a working artifact. This is the backbone of the entire roadmap and matches the blueprint's own Part C ordering exactly (it is not re-derived differently here — the blueprint's ordering is already correct; this document adds the section-level breakdown and solo-engineer pacing on top of it).

### 2.2 Independent Branches (Order Among These Is a Preference, Not a Requirement)

Once Phase 10 (Workflow Policy Engine) and Phase 11 (RI at Scale, which only needs Phase 03 proven — it does not need Phases 04–10) are reachable, the remaining four phases — **11/12 (scale + context), 13 (advanced QA), 14 (MCP integrations), 15 (evaluation)** — have no dependencies on each other. A solo engineer can:

- Build 11→12 early (right after Phase 03 is proven) if repo scale is the more interesting/urgent research question, *before* finishing 04–10. This is explicitly valid — §G.4's federation work only reads from the RI interface built in Phase 03, it does not require any agent to exist.
- Or build 13, 14, 15 in any relative order once their stated dependency is met, based on whichever is most valuable to demonstrate next (e.g., MCP integrations (14) if the next demo needs to show a real GitHub PR; evaluation (15) if the next demo needs to show KPI trends).

**Recommended default order** (if no external pressure dictates otherwise): 00→01→02→03→04→05→06→07→08→09→10→11→12→13→14→15→16 (i.e., the numeric order used throughout this doc set) — because it maximizes "always demoable, always increasing in agent sophistication" and defers the more open-ended research phases (11, 12, 15) until the core loop (00–10) is trustworthy enough to generate real signal for them. Deviate deliberately, not by default.

### 2.3 Why Phases 11–15 Are *Not* Interleaved Into 00–10

It would be tempting to build Repo Intelligence at Scale (11) or Advanced QA (13) immediately after their narrow prerequisite is met, interleaved with earlier phases. This is deliberately avoided for one reason: **Phases 00–10 are the phases that prove the safety model works at all** (fail-closed defaults, real interrupt/resume, real validators, real approval gates). Every hour spent scaling retrieval or deepening QA before that loop is proven is an hour that could be invalidated by a design flaw discovered in the core loop. Build the thin, safe, end-to-end path first; deepen each dimension (scale, context efficiency, QA depth, integrations, measurement) only after it's proven correct end-to-end at small scale.

### 2.4 Fail-Closed Defaults Before Phase 10

Phases 05–09 run real agents through real phases, but **before Phase 10 exists, every task uses the conservative default profile** (`WorkflowProfile.most_conservative()`, §F.1 — explicit values: all agents active, `qa_depth=standard`, all checkpoints including scope/design/release/pr/deployment, `max_parallelism=2`, `cost_budget_usd=20.0`) — meaning every checkpoint requires approval and QA runs at standard depth regardless of computed risk/confidence. This is intentional, not a stopgap to feel bad about: it is the fail-closed principle (Principle 8) applied to the *build process itself*. Do not attempt to hand-code shortcut paths ("skip approval if risk is obviously low") into individual agents during Phases 05–09 — that logic belongs exclusively in `workflow_engine/policy.py`, built once, correctly, in Phase 10.

---

## 3. Research-Heavy vs. Foundation-Heavy Modules

Useful lens for pacing effort and setting expectations per phase:

| Classification | Phases | Why |
|---|---|---|
| **Foundation-heavy** (get this exactly right; low ambiguity, high consequence of error) | 00, 01, 02, 08, 10 | Safety scaffolding, durability, model independence, approval governance, and routing logic are all things where a subtle bug is a safety incident, not a bad user experience. Time spent here is not "slow," it's proportionate. |
| **Balanced** (real engineering judgment calls, moderate ambiguity) | 03, 05, 06, 07, 09, 14 | Real design decisions exist (which retrieval fusion method, how granular a CodeGen sub-agent should be) but the blueprint gives strong guidance and there's a clear "does it work" test. |
| **Research-heavy** (expect iteration; first attempt is a baseline, not a final answer) | 04 (question bank tuning), 11 (shard boundary validation), 12 (compression effectiveness), 15 (confidence recalibration, golden dataset construction) | These involve empirical tuning against data that doesn't exist until you generate it. Budget for a "build v1, measure, revise" loop rather than expecting the first implementation to be final. |
| **Depth-add, not core-path** (system already works without these; they make it better/safer/faster) | 13, 16 | The system is functionally complete and demoable after Phase 10. 13 and 16 (and 15) are about *trust and robustness at scale*, not new core capability. |

---

## 4. Cross-Phase Consistency Rules

A few rules apply across every phase and are stated once here rather than repeated 17 times:

1. **Every phase must leave `main` in a runnable state.** `docker-compose up && make migrate && make dev` must work at the end of every phase, from a clean checkout.
2. **No phase silently disables a safety mechanism from an earlier phase.** If Phase 10's routing logic needs to loosen an approval requirement Phase 08 made unconditional, that loosening must be an explicit, tested rule in `resolve_workflow_profile()` — never a quiet removal of the earlier check.
3. **Every new agent, from Phase 05 onward, is a `ModelAdapter` consumer and a MASC-validated node** — no exceptions "just for this one simple agent." Consistency here is what makes Phase 16's chaos tests and Phase 15's evaluation pipeline able to reason about *every* agent uniformly.
4. **Section acceptance criteria are the source of truth for "done," not this roadmap's one-line summaries.** This document is a map; `phases/phase-NN/section-XX.md` is the territory.

---

## 5. Ready for Repository Initialization — Summary

This roadmap is documentation-only by design (see brief). The next step — actual repository scaffolding — should produce exactly the following, and nothing more, before Phase 00's first atomic task begins:

### 5.1 What Repository Initialization Should Create

1. **Directory skeleton** matching `final_plan.md` §Q, but populated only with the pieces Phase 00 actually needs on day one — do not pre-create empty directories for Phase 14's `mcp_integrations/` or Phase 9's `ui/` before those phases start. Minimum viable skeleton for Phase 00:
   ```
   sdlc-platform/
   ├── apps/api/                 # FastAPI app, empty router
   ├── apps/worker/               # ARQ worker entrypoint stub
   ├── packages/common/           # Task model lands here first
   ├── tests/unit/
   ├── tests/integration/
   ├── configs/                   # empty, ready for Phase 4's question_bank/, Phase 10's workflow_policies/
   ├── db/migrations/              # Alembic init, no models yet
   ├── docker-compose.yml          # Postgres (pgvector-enabled) + Redis
   ├── pyproject.toml              # uv-managed, Python 3.12
   ├── Makefile                    # up / migrate / test / dev targets
   ├── .env.example
   └── README.md                   # points back to this docs/ set
   ```
2. **`pyproject.toml`** with the Phase 00 dependency set only: `pydantic`, `fastapi`, `sqlalchemy[asyncio]`, `alembic`, `asyncpg`, `redis`, `arq`, `opentelemetry-sdk`, `structlog`, `pytest`, `pytest-asyncio`, `ruff`, `mypy`. Do **not** add `langgraph`, `langchain-core`, Tree-sitter/Zoekt bindings, or any model-provider SDK yet — those arrive with Phases 01, 02, and 03 respectively, each as its own atomic task, so the dependency graph documents the build order as it grows.
3. **`docker-compose.yml`** with Postgres 16 (pgvector extension pre-enabled via init script, even though nothing uses it until Phase 3 — enabling the extension is a one-line Phase 00 task, using it is not) and Redis 7.2. No Langfuse container yet unless you want tracing visualization from day one (recommended but optional per `techstack.md` §7).
4. **`.env.example`** documenting: `DATABASE_URL`, `REDIS_URL`, and placeholders for secrets that don't exist yet (commented out, not fabricated).
5. **CI skeleton** (GitHub Actions or equivalent) running `ruff check`, `mypy`, and `pytest tests/unit` on every push — this is itself a Phase 00 atomic task (see `phases/phase-00/section-06.md`), not pre-existing tooling to take for granted.

### 5.2 What Repository Initialization Should Explicitly NOT Create

- No agent code, no LangGraph graphs, no prompts — these are Phase 01/05+ work.
- No UI project — Phase 09 work; creating it early invites premature frontend decisions before backend shapes stabilize.
- No MCP client code — Phase 14 work.
- No `model_adapters/` implementation beyond the empty package directory — the `ModelAdapter` Protocol itself is Phase 02's first atomic task, not a scaffolding concern.

### 5.3 First Three Atomic Tasks After Scaffolding (Pointer, Not Duplicate — Full Detail in Phase 00)

1. `packages/common/task.py` — the `Task`, `WorkType`, `Methodology`, `RiskTier`, `TaskState`, `RepoRef`, `TaskBudget`, `ApprovalRecord` Pydantic models exactly as specified in §B.1.
2. `db/migrations/` initial Alembic revision creating the `tasks` table (§R) from the `Task` model.
3. A single passing test: construct a `Task`, persist it, reload it, assert equality — the smallest possible end-to-end proof the foundation is wired correctly.

This is intentionally the very first thing built (see `phases/phase-00/section-01.md` for full detail) — the blueprint's own closing line makes the same call: *"Implementation starts at §B.1 (Task Data Model)."*
