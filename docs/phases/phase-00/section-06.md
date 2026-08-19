# Section 06 — Job Queue Scaffolding & CI Pipeline

## Objective

Stand up the Redis Streams + ARQ worker scaffolding (no real jobs yet — just the runtime and a trivial proof-of-life job) and a CI pipeline enforcing lint/type/test on every push, closing out Phase 00's foundation.

## Why It Exists

Phase 01's LangGraph execution will run inside this worker process. Building the worker runtime now — separate from any graph logic — means Phase 01 only has to add graph execution to an already-proven async job-processing loop, rather than standing up both at once. A CI pipeline from the very first commit is what makes "every phase leaves `main` runnable" (a hard rule in `development_strategy.md`) actually enforced rather than aspirational.

## Expected Architecture

`apps/worker/main.py` configures an ARQ `WorkerSettings` against the Redis instance from Phase 00 Section 02, with a single trivial registered function (e.g., `ping_task(ctx, task_id)` that records a trace event and returns). GitHub Actions (or equivalent) workflow runs `ruff check`, `mypy`, `pytest tests/unit`, and the Alembic drift check from Section 02 on every push and PR.

## Dependencies

Section 02 (Redis config), Section 05 (trace emission from within the worker job).

## Atomic Implementation Tasks

1. Implement `apps/worker/main.py` with ARQ `WorkerSettings`, Redis connection from `packages/common/config.py`.
2. Implement one trivial job function that: emits a trace event, optionally records a `cost_tracking` row with zero cost (proving the worker can reach both Postgres and the tracer), and returns a result.
3. Implement `apps/api/main.py` as a minimal FastAPI app with a single `/health` endpoint (checks Postgres + Redis connectivity) — this is the seed of Phase 01's API, built now because "is the system up" is a Phase 00 concern.
4. Write the CI workflow: lint, type-check, unit tests, Alembic autogenerate-diff check, all against a service-container Postgres+Redis. Include a grep step: `opentelemetry` imports only allowed in `packages/common/tracing.py`.
5. Write the `Makefile` targets: `up`, `migrate`, `test`, `dev` (runs API + worker concurrently via a process manager or two terminal commands documented in the README).
6. End-to-end integration test: enqueue the trivial job via ARQ's client, confirm the worker processes it and the expected trace/DB side effects occur.

## Manual Testing Procedure

1. `make up && make migrate`.
2. `make dev` (or run API and worker in two terminals).
3. `curl localhost:8000/health` — confirm `{"status": "ok", "db": "ok", "redis": "ok"}` or equivalent.
4. Enqueue the trivial job (via a small script using the ARQ client) and confirm the worker log shows it processing, and the trace/DB side effects appear.
5. Push a branch with a deliberate lint error and confirm CI fails; fix it and confirm CI passes.

## Expected Demo

This is Phase 00's overall demo, assembled from all six sections: `scripts/demo_phase0.py` run end-to-end from a clean `docker-compose up`, producing a printed trace of: Task created → persisted → sandboxed job run → cost recorded → budget checked → (optionally) job routed through the worker queue — with a final printout of the `tasks` and `cost_tracking` rows from Postgres.

## Acceptance Criteria

- [ ] `/health` endpoint accurately reflects Postgres/Redis connectivity.
- [ ] A job enqueued via ARQ is processed by the worker and its side effects (trace + optional DB row) are verifiable.
- [ ] CI pipeline fails on lint, type, or test errors, and on Alembic schema drift — each verified by deliberately introducing one and confirming the failure.
- [ ] `docker-compose up && make migrate && make dev` works from a completely clean checkout (the "no phase leaves `main` unrunnable" rule, verified for the first time here).

## Risks

- **Risk:** CI service-container setup (Postgres+Redis) diverging from local `docker-compose.yml` config, causing "works in CI, fails locally" or vice versa. **Mitigation:** keep CI's service container versions pinned identically to `docker-compose.yml`; consider generating one from the other if drift becomes a recurring problem.

## Future Improvements

- Consumer-group partitioning by risk tier — Phase 16 (needs risk tiers to be meaningful first, which needs Phase 10).
- Dockerized worker deployment for production — deferred until an actual deployment target exists.

## Research Opportunities

None — this section closes out Phase 00's infrastructure; the interesting work starts in Phase 01.
