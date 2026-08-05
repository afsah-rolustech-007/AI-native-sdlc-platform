# Section 02 — PostgreSQL Checkpointer & thread_id Handling

## Objective

Wire LangGraph's `AsyncPostgresSaver` as the checkpointer for the stub graph from Section 01, using `task.id[:255]` as the LangGraph `thread_id`, and prove that graph state is durably persisted after every node.

## Why It Exists

This is the mechanism that makes crash recovery (Section 04) and interrupt/resume (Section 03) possible at all. LangGraph's default in-memory checkpointer loses all state on process restart — unacceptable for a platform where tasks may span hours and must survive worker restarts/deploys. The `id[:255]` truncation rule exists because LangGraph's `thread_id` has practical length constraints in some backends, and the blueprint calls this out explicitly (§B.1: "PostgreSQL constraint enforced here") — get the truncation/collision handling right now, since Task IDs are otherwise unconstrained in length at the application layer... actually they're already capped at 255 by the Task model (Phase 00 Section 01), so this section's job is to *use* that same value consistently as `thread_id`, not to re-derive a different truncation.

## Expected Architecture

`packages/orchestration/checkpointers/postgres.py` configures `AsyncPostgresSaver.from_conn_string(...)` against the same Postgres instance as the rest of the platform (reusing `packages/common/config.py`'s `DATABASE_URL`). The checkpointer's own tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes` — LangGraph-managed, per §R's comment) are created via the saver's own setup method, run once via a startup task (or a dedicated `scripts/init_langgraph_tables.py`).

## Dependencies

Section 01 (compiled graph to attach the checkpointer to), Phase 00 Section 02 (Postgres instance).

## Atomic Implementation Tasks

1. Add the LangGraph Postgres checkpointer dependency (`langgraph-checkpoint-postgres` or equivalent) to `pyproject.toml` — this is the first LangGraph-family dependency added to the project (per `roadmap.md` §5.2, deliberately not added in Phase 00's scaffolding).
2. Implement checkpointer setup/initialization (creating LangGraph's own tables) as an idempotent startup step.
3. Compile the Section 01 graph `with checkpointer=...` and confirm `.invoke(config={"configurable": {"thread_id": task.id}})` persists checkpoints.
4. Write a helper `get_thread_id(task: Task) -> str` that returns `task.id` (already ≤255 chars by construction) — document explicitly that no further truncation happens here because Phase 00 already enforces the constraint at the source.
5. Integration test: run the graph to completion, inspect the `checkpoints` table directly via SQL, confirm one or more checkpoint rows exist for the `thread_id`, and confirm `graph.get_state(config)` returns the expected final state after the process "restarts" (new process/connection, same `thread_id`).

## Manual Testing Procedure

1. Run the stub graph to completion for a given task.
2. Query `SELECT thread_id, count(*) FROM checkpoints GROUP BY thread_id;` and confirm a checkpoint trail exists.
3. In a fresh Python process (simulating restart), call `graph.get_state(config)` for the same `thread_id` and confirm it returns the completed state without re-running any node.

## Expected Demo

Terminal session: run graph in process A, exit process A, start process B, fetch state by `thread_id` in process B, print it — showing state survived a full process restart.

## Acceptance Criteria

- [ ] Checkpoints are written to Postgres after every node execution (verified via direct SQL query, not just trusting the API).
- [ ] State is retrievable by `thread_id` from a completely new process/connection.
- [ ] `thread_id` is always exactly `task.id`, with the length invariant explicitly re-asserted here (test constructs a `Task` at the 255-char boundary and confirms no silent truncation occurs at this layer).

## Risks

- **Risk:** LangGraph checkpoint table growth is unbounded by default — not a Phase 01 problem to solve, but worth noting now. **Mitigation:** flag as a future improvement (below); do not build retention logic prematurely.

## Future Improvements

- Checkpoint retention/pruning policy — revisit once real task volume exists (post Phase 05), informed by actual storage growth data.
- Postgres primary+replica HA for the checkpointer specifically — Phase 16 (chaos-tested failover).

## Research Opportunities

None — this is a "use the library correctly" section, not a design question.
