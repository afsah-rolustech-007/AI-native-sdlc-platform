# Section 01 — Task Data Model & Persistence

## Objective

Implement the `Task` Pydantic model and its supporting enums/sub-models exactly as specified in `final_plan.md` §B.1, and make it round-trip through Postgres.

## Why It Exists

`Task` is, per the blueprint, "the single most important structural decision" — every other subsystem (routing, memory, feedback loops, approvals, evaluation) references it. Nothing else in the roadmap can be built correctly until this exists and is proven durable.

## Expected Architecture

`Task` is a runtime-validated Pydantic `BaseModel`, not a `TypedDict` — the blueprint is explicit about why (§B.1: "TypedDicts validate at type-check time only. Pydantic validates at runtime — the right behavior for a safety-critical object."). It lives in `packages/common/task.py`, imported by literally every other package. No business logic lives on the model itself beyond field validation — routing/policy logic belongs in `workflow_engine/` (Phase 10), not here.

## Dependencies

None (root of the dependency graph).

## Atomic Implementation Tasks

1. Implement `WorkType`, `Methodology`, `RiskTier`, `TaskState` enums exactly per §B.1 (string enums, exact member names — other phases will pattern-match on these literal values).
2. Implement `RepoRef`, `TaskBudget`, `ApprovalRecord` sub-models per §B.1, including default values (`token_ceiling=2_000_000`, `cost_ceiling_usd=20.0`, `max_retries_per_node=3`).
3. Implement the `Task` model itself, including the `id: str = Field(max_length=255)` constraint (this exact constraint is referenced later by the Postgres schema and by LangGraph's `thread_id` truncation in Phase 01 — do not loosen it).
4. Write a `packages/common/task_repository.py` with `create_task`, `get_task`, `update_task_state` async functions against SQLAlchemy (depends on Section 02's schema existing — implement the interface here, wire the migration in parallel).
5. Unit tests: every enum member constructs; `Task` rejects an id > 255 chars; `Task` serializes/deserializes to/from dict without field loss (round-trip test).

## Manual Testing Procedure

1. In a Python REPL (or a throwaway script), construct a `Task` with minimal required fields and print `task.model_dump_json(indent=2)`.
2. Attempt to construct a `Task` with a 256-character `id` and confirm Pydantic raises a `ValidationError`.
3. Confirm default `TaskBudget` values appear when not explicitly provided.

## Expected Demo

Terminal output showing a constructed `Task`'s full JSON representation, followed by a caught `ValidationError` for the oversized-id case — proving both the happy path and the safety constraint work.

## Acceptance Criteria

- [ ] `Task` model matches every field in §B.1 exactly (name, type, default).
- [ ] `id` field enforces `max_length=255` and this is unit-tested.
- [ ] `Task` round-trips through `model_dump()` / `model_validate()` with zero field loss.
- [ ] 100% of enum members from §B.1 are implemented (no partial enums "to be added later").

## Risks

- **Risk:** Silently drifting from the blueprint's field names/types as later phases need "just one more field," causing schema mismatches with §R's SQL definition. **Mitigation:** treat §B.1 as the source of truth; any field addition is a deliberate, documented decision (see `development_strategy.md` §7 on the decisions log), not an ad hoc addition.

## Future Improvements

- Add a `Task.from_ticket_import()` factory once Phase 14's Jira MCP integration exists — not needed yet.

## Research Opportunities

None — this section is intentionally the least ambiguous part of the entire roadmap. Get it exactly right and move on.
