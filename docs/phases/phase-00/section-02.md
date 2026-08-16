# Section 02 — Database Schema, Migrations & Config Management

## Objective

Stand up PostgreSQL 16 (with the `pgvector` extension enabled, even though unused until Phase 3), create the initial Alembic migration for the tables Phase 00 needs (`tasks`, `cost_tracking`; scaffold `hitl_log` and `approvals` now since their shape is stable per §R even though nothing writes to them until Phase 08), and establish the project's config/secrets loading pattern.

## Why It Exists

Every phase from here on needs a database and a consistent way to load configuration (`DATABASE_URL`, `REDIS_URL`, later model API keys). Doing this once, correctly, with migrations from day one (rather than hand-editing schema) is what keeps 17 phases of schema evolution (§R grows continuously) manageable solo.

## Expected Architecture

SQLAlchemy 2.0 async models mirror the tables in §R. Alembic manages migrations under `db/migrations/`. A single `packages/common/config.py` module (Pydantic `BaseSettings`) reads environment variables once and is imported everywhere else needs config — no direct `os.environ` reads scattered through the codebase.

## Dependencies

Section 01 (Task model shape determines the `tasks` table columns).

## Atomic Implementation Tasks

1. Write `docker-compose.yml` with a `postgres:16` service, mounting an init script that runs `CREATE EXTENSION IF NOT EXISTS vector;`, and a `redis:7.2` service.
2. Implement `packages/common/config.py` — a Pydantic `Settings` class reading `DATABASE_URL`, `REDIS_URL`, `ENVIRONMENT` from `.env` via `pydantic-settings`.
3. Implement SQLAlchemy async engine/session setup in `packages/common/db.py`.
4. Define SQLAlchemy models for `tasks` and `cost_tracking` per §R's column definitions; scaffold (but don't populate) `approvals` and `hitl_log` table models — **`hitl_log` must include `request_type`** per §R (CHECK constraint on the four HITL discriminant values).
5. Generate the initial Alembic revision (`alembic revision --autogenerate`) and verify the generated SQL matches §R's `CREATE TABLE` statements column-for-column.
6. Add the indexes from §R (`idx_tasks_state`, `idx_tasks_risk_tier`, `idx_cost_task_id`, `idx_hitl_request_type`) to the same migration.
7. Write an integration test (using a real Postgres via `docker-compose` or testcontainers) that runs migrations up, inserts a `Task`, reads it back via `task_repository.get_task`.

## Manual Testing Procedure

1. `docker-compose up -d postgres redis`.
2. `alembic upgrade head` — confirm it completes without error.
3. `psql` into the container and run `\dt` — confirm all four tables exist; run `\d tasks` and diff columns against §R by eye.
4. Run the Section 01 demo script against this real database instead of an in-memory stub.

## Expected Demo

A terminal recording: `docker-compose up -d`, `alembic upgrade head`, then a script that creates and re-fetches a `Task` from the real database, printing the row.

## Acceptance Criteria

- [ ] `alembic upgrade head` runs cleanly from an empty database.
- [ ] `alembic downgrade base` also runs cleanly (migrations are reversible) — verified explicitly, not assumed.
- [ ] All table/column/index definitions match §R (including `hitl_log.request_type` and `idx_hitl_request_type`).
- [ ] `pgvector` extension is enabled and verifiable via `SELECT * FROM pg_extension;`, even though no vector column exists yet.
- [ ] No code outside `packages/common/config.py` reads `os.environ` directly (grep-verifiable).

## Risks

- **Risk:** Schema drift between what SQLAlchemy models declare and what migrations actually apply, if migrations are hand-edited without re-running autogenerate diff checks. **Mitigation:** CI step (Section 06) that runs `alembic check` (or equivalent autogenerate-diff check) to catch drift.

## Future Improvements

- Read/write replica split for Postgres — explicitly deferred to Phase 11 per §N (SPOF row); do not build this now.

## Research Opportunities

None.
