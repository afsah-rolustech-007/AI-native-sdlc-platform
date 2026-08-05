# Technology Stack — Recommendation & Rationale

This document evaluates the user-proposed stack against the blueprint's own recommendations (`final_plan.md` §O) and against alternatives, and gives a final decision per component. Where the proposed stack and the blueprint agree, the reasoning is stated once and adopted. Where a critical evaluation suggests a variant, it's called out explicitly with trade-offs.

**Bottom line: the proposed stack (Python/FastAPI/LangGraph/PostgreSQL/SQLAlchemy/Alembic/Redis + React/Vite/TS/Tailwind/shadcn) is correct and is adopted almost verbatim.** The blueprint independently arrives at the same core choices (§O). The additions below (SQLAlchemy, Alembic, specific libraries) fill gaps the blueprint leaves implicit.

---

## 1. Backend Core

| Component | Decision | Version (start) | Rationale | Alternatives Considered |
|---|---|---|---|---|
| **Language** | Python | 3.12 | LangGraph and the entire agent ecosystem (LangChain, MCP SDK, Tree-sitter bindings) are Python-first. Modern async/typing features (3.12) reduce boilerplate in agent code. | Node/TypeScript backend — rejected: LangGraph's Python implementation is the reference implementation with the most mature checkpointing, `Send` API, and interrupt/resume support. The JS port lags. |
| **Orchestration** | LangGraph + LangChain core | 0.3+ | Mandated by the blueprint and by the project's own design (native HITL via `interrupt()`, native durable checkpointing, native `Send` API for fan-out). Rebuilding this on a generic task queue would mean re-inventing checkpointing and interrupt semantics — not a good use of a solo engineer's time. | Temporal (flagged in blueprint §P3 as a *future* durability backbone for multi-day tasks — not needed at MVP scale; adds an entire second orchestration paradigm to learn). Plain Celery/DAG libraries — rejected: no native interrupt/resume, no native state-diffing checkpoints. |
| **API framework** | FastAPI | 0.111+ | Async-native, matches LangGraph's async execution model directly (no event-loop bridging). Pydantic-native, which matters because the Task model (§B.1) *is* Pydantic. Automatic OpenAPI schema doubles as living API docs for a solo engineer. | Django — rejected: sync-first ORM/request model fights LangGraph's async nodes; heavier than needed for what is intentionally "a thin read layer" (§P) plus a task-submission API. |
| **Primary database** | PostgreSQL | 16 | One database serves four roles at MVP: LangGraph checkpoint store, Task/approval/audit tables (§R), pgvector semantic store, and episodic memory. This is *intentionally* a single point of coupling at MVP — the blueprint explicitly flags it (§N, SPOF row) and defers the split until Repo Intelligence at Scale (Phase 11) actually needs read/write-pattern separation. Don't pre-split; the blueprint is right that early splitting is premature optimization for a single-engineer MVP. | MySQL — rejected: no first-class pgvector-equivalent extension ecosystem, weaker native JSON/JSONB support used throughout the Task/QAEvidence schemas. |
| **ORM** | SQLAlchemy 2.0 (async) | 2.0+ | Not named explicitly in blueprint §O but implied by the `db/migrations` (Alembic) directory in §Q and is the natural pairing. SQLAlchemy 2.0's async engine matches FastAPI/LangGraph's async model. Gives typed query building against the exact tables in §R without hand-rolled SQL for every access pattern, while still allowing raw SQL/`text()` for the handful of performance-sensitive queries (e.g., pgvector similarity search) where the ORM adds no value. | Raw `asyncpg` everywhere — rejected: fine for pgvector queries specifically (and used there directly per Phase 3), but hand-writing SQL for the full Task/approval/audit CRUD surface is more error-prone and slower to evolve than SQLAlchemy models, for no real performance benefit at this scale. Prisma-style codegen ORMs — not mature enough in the Python ecosystem to prefer over SQLAlchemy. |
| **Migrations** | Alembic | 1.13+ | Standard companion to SQLAlchemy; explicitly named as the migration tool in §Q (`db/migrations/`). Auto-generates migrations from model diffs, which matters because the schema (§R) evolves across almost every phase (new tables for cost tracking, evaluation results, feedback loop events, etc.). | Hand-written SQL migrations only — rejected: loses diff-based autogeneration, more error-prone as the schema grows across 17 phases. |
| **Job queue / worker** | Redis Streams + ARQ | Redis 7.2+, ARQ 0.25+ | Matches §O exactly. Redis Streams gives consumer-group partitioning — required later (Phase 16) for risk-tier queue isolation (a Critical-risk task must never be starved by a flood of Low-risk tasks). ARQ is a lightweight async worker framework that pairs naturally with FastAPI/asyncio — no separate sync worker runtime to operate. | RabbitMQ — viable alternative named in §O; not chosen because Redis is already required for caching, so Redis Streams avoids operating a second piece of broker infrastructure at MVP. Celery — heavier, sync-first by default, more operational surface than a solo engineer needs for the actual concurrency levels at MVP scale. |
| **Cache** | Redis | 7.2+ | Same instance family as the queue at MVP (separate logical DB index); hot RI query results and UI session state. | — |

---

## 2. Repository Intelligence & Retrieval Stack

The blueprint's own comparative analysis (§0.1, §G.3) already did the hard evaluation work here (Zoekt over SCIP, NetworkX→Neo4j over KuzuDB, pgvector→Qdrant over Pinecone). This roadmap adopts those conclusions as-is; restated briefly with the MVP/scale split made explicit, since that split is itself an implementation-order decision (Phase 3 vs. Phase 11):

| Component | MVP (Phase 3) | At Scale (Phase 11) | Why the Split Is Safe |
|---|---|---|---|
| AST/symbol parsing | Tree-sitter | Tree-sitter (unchanged) | Multi-language, embeddable, fast incremental — correct at any scale, no migration needed. |
| Lexical/code search | Zoekt | Zoekt (unchanged) | Trigram index is O(1) query regardless of repo size once built; proven at Sourcegraph scale. |
| Dependency/call graph | NetworkX (in-process) | Neo4j | NetworkX has zero infra cost and is perfectly adequate for graphs that fit in memory (small/medium repos). The `RepositoryIntelligence` interface (§G.6) is the seam — agents never touch the graph client directly, so this swap is invisible to every agent built in Phases 4–10. |
| Vector search | pgvector | Qdrant | pgvector reuses the already-running Postgres instance at MVP (one less service to operate solo). Qdrant is purpose-built ANN with horizontal scaling for when 1M-file embedding volume makes pgvector's index rebuild cost a bottleneck. |
| Deep security semantic | — (not active at MVP) | CodeQL | Deferred to Phase 13 (Advanced QA) — periodic deep dataflow scanning is a QA-depth concern, not a Phase 3 retrieval concern. |

**Critical evaluation note:** the blueprint's rejection of SCIP as a "search engine" (§0.2 #5) and of KuzuDB as an embedded-only graph store (§0.2 #4) are both correct calls and are adopted without modification — SCIP is a symbol-export protocol, not a query engine, and KuzuDB's embedded model is a genuine architectural mismatch for a service designed to be queried concurrently across tasks (§G.1).

---

## 3. Model Layer

| Component | Decision | Rationale |
|---|---|---|
| **Adapter base** | `langchain_core.language_models.BaseChatModel` | Already a LangGraph dependency; structured output, tool-calling, streaming, and retry semantics come essentially for free (§I.1). Building a bespoke adapter interface from scratch would mean re-implementing all of that. |
| **Primary provider** | GLM (GLM-4.7 / GLM-4.7-Flash) | Per blueprint assumption — **must verify OpenAI-compatibility against live docs before Phase 2 implementation** (§I.1, explicitly flagged as unverified). If verified compatible, the adapter is a thin `ChatOpenAI`-compatible wrapper. |
| **Normalization fallback** | LiteLLM (optional) | Only introduced if GLM's endpoint has compatibility gaps discovered during Phase 2. Not built speculatively — YAGNI until the verification step in Phase 2 §I.1 says otherwise. |
| **Second provider (proof of independence)** | Any second adapter (e.g., a widely available OpenAI-compatible model) | Required in Phase 16 specifically to *prove* the `ModelAdapter` abstraction has zero leaks — not chosen for its capabilities, chosen because it's a different vendor. |

---

## 4. Frontend

| Component | Decision | Version | Rationale |
|---|---|---|---|
| **Framework** | React | 18+ | Matches the proposed stack; largest ecosystem for the kind of live-updating, WebSocket-driven dashboard this UI is (§P). |
| **Build tool** | Vite | 5+ | Fast dev server and HMR matter for a solo engineer iterating on 12 screens; far lower config overhead than Webpack. |
| **Language** | TypeScript | 5+ | The WebSocket `AgentEvent` protocol (§P) and REST responses are typed on the backend (Pydantic) — TypeScript types generated/mirrored from the OpenAPI schema keep the two in sync without manual duplication. |
| **Styling** | Tailwind CSS | 3+ | Fast to iterate without context-switching to separate CSS files — appropriate given the explicit instruction to keep the frontend "intentionally simple but fully functional" while backend research is the priority. |
| **Component library** | shadcn/ui | latest | Copy-in (not npm-dependency) component model means no black-box UI library to fight when the 12 screens need small deviations (e.g., timeout countdowns, canary charts). Accessible-by-default primitives reduce the axe-core (accessibility QA, §K.1) burden later. |
| **Data fetching / realtime** | Native `fetch` + typed client for REST; native `WebSocket` wrapped in a `useWebSocket` hook for the `AgentEvent` stream (§P) | No heavyweight state-management library (Redux, etc.) is justified for a "thin read layer over existing backend objects" (§P) — React Query (TanStack Query) is the one addition worth making, for its cache-and-refetch semantics on the REST side, paired with the WebSocket hook for push events. |

**Explicit non-goals for the frontend, matching the brief:** no server-side rendering, no design system beyond shadcn defaults, no offline support, no mobile-specific layout work. The UI's job is legibility of what the backend is doing — not a polished product surface.

---

## 5. Observability, QA Tooling, and Supporting Libraries

These are adopted directly from the blueprint's own tech stack table (§O) without modification — the blueprint's reasoning for each is already sound and specific to this project's needs (e.g., Zoekt's proven scale, ruff replacing three tools, uv's speed). Restated here in one place for a single reference document:

| Category | Tool | Notes |
|---|---|---|
| Tracing | OpenTelemetry SDK 1.25+ | Per-node spans; the backbone Phase 0 builds first. |
| Agent trace visualization | Langfuse (self-hosted) 2.x | Token cost per agent per task — critical for a solo engineer debugging agent behavior. |
| Metrics / Dashboards | Prometheus 2.52+ / Grafana 10.x | System + KPI dashboards; only becomes load-bearing from Phase 15 (Evaluation) onward, but the OTel plumbing exists from Phase 0. |
| Logging | structlog 24.x | Structured JSON into the same OTel pipeline. |
| Static analysis | ruff 0.4+, mypy 1.10+ | ruff replaces flake8+black+isort in one tool — meaningfully less config for a solo engineer. |
| Security (inline) | Semgrep 1.70+ | Fast, pattern-based, runs inline during QA (Phase 13). |
| Security (deep) | CodeQL latest | Periodic dataflow analysis (Phase 13) — catches classes of bugs Semgrep's pattern matching structurally cannot. |
| Secrets scanning | detect-secrets 1.5+ | Pre-commit + CI, and the pre-context-assembly filter (§B.6). |
| Dependency audit | pip-audit + OSV-Scanner/Trivy | CVE + license scanning (Phase 13). |
| Mutation testing | mutmut (Python) | Critical-path modules only, High risk tier (Phase 13) — expensive, deliberately scoped narrow. |
| Property-based testing | Hypothesis 6.100+ | Pure functions/parsers (Phase 13). |
| API fuzzing | schemathesis 3.27+ | OpenAPI-contract-driven (Phase 13). |
| Load testing | k6 or Locust | Performance QA, High+ risk only (Phase 13). |
| UI testing | Playwright 1.44+ | Browser automation for UI QA (Phase 13). |
| Accessibility | axe-core | WCAG 2.1 (Phase 13). |
| Package management (Python) | uv 0.2+ | Materially faster than pip/poetry for a solo engineer's iteration loop. |
| MCP client | `mcp` Python SDK 1.x | Official client (Phase 14). |
| Auth (human UI) | OAuth2/OIDC via org identity provider | Kept separate from agent service tokens (§B.6) — do not conflate human auth with the short-lived, task-scoped git/tool credentials agents use. |
| IaC | Terraform (or org standard) | All provisioning; agents never call cloud APIs directly (§B.6, §J.1). Not required until real deployment targets exist — introduced pragmatically, not spun up speculatively. |

---

## 6. Explicit Rejections (and Why)

Documenting what was *not* chosen matters as much as what was, so future-you doesn't re-litigate these:

- **Multi-tenancy infrastructure at MVP** — explicitly a non-goal (§A.3). No tenant-scoping schema work until requested.
- **Kubernetes at MVP** — named as a P3/future item (§O's IaC row, §T P3). A solo engineer running `docker-compose` locally and a single deploy target is the right scope; Kubernetes is operational overhead with no payoff until horizontal worker scaling is an actual bottleneck (signal: queue depth metrics from Phase 16's load test).
- **A learned/ML-based router in place of `resolve_workflow_profile()`** — deliberately rejected by the blueprint itself (Principle 5, §A.2) in favor of an auditable, unit-testable rule function. This is a safety-motivated choice, not a laziness one — do not "upgrade" it to ML without a very strong evaluation-driven reason and a lot of golden-dataset evidence (§L.3).
- **A second vector DB or graph DB "just in case" at MVP** — YAGNI. pgvector and NetworkX are correct until Phase 11's actual scale-driven trigger.

---

## 7. Environment & Local Development Baseline

Established in Phase 0, referenced by every later phase:

- `docker-compose.yml`: PostgreSQL 16 (with pgvector extension enabled), Redis 7.2, Langfuse (self-hosted, optional but recommended from Phase 0 so trace visualization exists from day one).
- `pyproject.toml` managed via `uv`.
- `.env.example` documents every required secret/config key as it's introduced — never let this drift from what the code actually reads.
- A single `Makefile` (or equivalent task runner) wraps the common loop: `make up` (docker-compose), `make migrate` (alembic), `make test`, `make dev` (API + worker + UI concurrently). This is worth the 30 minutes it takes in Phase 0 — it is what makes the "Plan → Implement → Run → Test → Verify → Demonstrate" loop (see `development_strategy.md`) fast enough to actually follow for 17 phases.
