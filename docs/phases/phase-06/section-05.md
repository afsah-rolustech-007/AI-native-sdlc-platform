# Section 05 — CodeGen Sub-agents & Parallel Fan-Out

## Objective

Implement the CodeGen sub-agent (§E.8: implements one module/scope per instance) and wire LangGraph's `Send` API to fan out N parallel instances per `TaskDecomposition`'s parallel groups — producing the platform's first real code diffs, executed inside Phase 00's sandbox.

## Why It Exists

This is the phase's central value-delivery mechanism. Parallel fan-out is what makes the platform's throughput scale with independent work rather than serializing everything — but it's also the first place genuine LangGraph mechanics (the `Send` API, fan-out/fan-in state merging) meet genuinely risky operations (executing generated code). Both halves need to be right together.

## Expected Architecture

`packages/agents/implementation/codegen_agent.py`'s `CodeGenAgent(BaseAgent)` takes one `TaskDecomposition` sub-task, uses progressive context expansion tools (§H.4 — `get_symbol_signature`, `get_symbol_body`, `get_callers`, `get_file_structure`, all from Phase 03, exposed as agent tool calls per §E.3's "Specialized Retrieval" for CodeGen) to gather only what it needs, generates a diff, and self-checks it (a lightweight, in-agent sanity pass) before returning. Model tier is Fast for simple modules, High-capability for complex refactors (§E.8) — the tier decision itself is a per-sub-task input from the Implementation Manager's decomposition (a reasonable heuristic: sub-task description/scope size), refined later by Phase 10's real routing. The `implementation` graph node uses `Send(codegen_node, {...sub_task...})` per parallel group in `TaskDecomposition.execution_order`, running true concurrent LangGraph branches; each branch runs its diff generation inside Phase 00's sandbox (write access scoped to a task-specific git branch/worktree, not the shared working tree).

**Every branch closes with a `WorkerCoordinationPacket` (§B.2/§D.9.2), not just a diff.** On successful exit, the agent's structured output includes the WCP fields (`assumptions`, `discovered_dependencies`, `interface_changes`, `risks`, `touches_files`, `confidence`, `needs_manager_attention`) alongside the diff — same model call, no extra round-trip. If the agent hits something Repository Intelligence can't resolve and its assumptions genuinely break, it emits a `ClarificationEscalation` (§B.2/§D.9.3) instead, sets `WorkerCoordinationPacket.blocked=true`, and **stops its own branch** — it does not guess, and it does not attempt to contact another CodeGen branch (there is no mechanism by which it could; §D.9.1). Section 06's Fan-in Coordinator is the sole consumer of both.

## Dependencies

Section 04 (`TaskDecomposition`), Phase 00 §04 (sandbox), Phase 03 (progressive context tools).

## Atomic Implementation Tasks

1. Implement `CodeGenAgent`'s tool-calling loop using the progressive context expansion tools from §H.4 — start with minimal context (Level 0 architecture summary only) and let the agent request more via tool calls, rather than force-injecting full file contents up front.
2. Implement diff generation and self-check (a lightweight in-agent review, distinct from the reflection pass in Section 02 — keep it cheap, this runs per sub-task, potentially many times per task).
3. Implement a task-scoped git worktree/branch strategy so parallel CodeGen instances write to isolated working copies, merged only at fan-in (Section 06) — this is a genuine design decision the blueprint doesn't fully specify at the git-mechanics level; document the chosen approach explicitly.
4. Wire the `Send` API fan-out in the `implementation` node: for each parallel group in `execution_order`, dispatch one `Send(codegen_node, sub_task)` per sub-task in that group, and let LangGraph handle native fan-in aggregation into `SDLCState.implementation_results` (the `append_only` reducer from Phase 01 §01 is exactly what makes this safe).
5. Run each CodeGen sub-agent's actual code execution/testing (if any at this stage — even a basic "does it parse/import" self-check) inside Phase 00's sandbox, tagged with the sub-task's identity for trace correlation.
6. Implement `WorkerCoordinationPacket` emission as part of the agent's structured output schema (§M.1), and the `ClarificationEscalation` early-exit path (consult RI first via the progressive-context tools; only escalate if still blocked) — write both to `SDLCState.worker_coordination_packets`/`clarification_escalations` (`append_only`) and reference the diff/logs via the Section 04 `BlackboardService`'s `store()`.
7. Integration test: the demo feature's 2–3 sub-tasks dispatch as real parallel `Send` branches (verified via trace timestamps showing overlapping execution, not accidental serialization), each producing a real diff against its isolated worktree, each with a well-formed `WorkerCoordinationPacket`.
8. Integration test: deliberately craft a sub-task whose module doesn't exist / whose assumed interface is wrong, confirm the agent consults RI first (`ri_consulted=true`), then emits a `ClarificationEscalation` and stops its branch cleanly rather than guessing or producing a diff against a false assumption.

## Manual Testing Procedure

1. Run the demo feature's Implementation phase and observe (via OTel traces) that independent sub-tasks' CodeGen agents genuinely overlap in execution time.
2. Inspect each generated diff for correctness against the design's stated requirements for that module.
3. Confirm each CodeGen agent's tool-call trace shows progressive expansion (starts minimal, requests more only as needed) rather than being handed the whole file upfront.

## Expected Demo

Terminal/trace output showing 2+ CodeGen sub-agents running concurrently (overlapping timestamps), each producing a diff, followed by a `git diff` view of the isolated worktrees before fan-in merges them.

## Acceptance Criteria

- [ ] Independent sub-tasks demonstrably execute in parallel (not accidentally serialized), verified via trace timing.
- [ ] Each CodeGen agent uses progressive context expansion (tool-call-driven), not eager full-context injection.
- [ ] Generated diffs are produced against isolated, task-scoped git worktrees — no direct writes to a shared working tree from concurrent agents.
- [ ] Every CodeGen execution runs inside Phase 00's sandbox, correctly attributed in traces.
- [ ] Every CodeGen branch (success or blocked) emits a schema-valid `WorkerCoordinationPacket`; a blocked branch's escalation shows `ri_consulted=true` before stopping.

## Risks

- **Risk:** Git worktree/branch management under real concurrency is a source of subtle bugs (race conditions, stale base commits). **Mitigation:** keep the isolation strategy as simple as possible at this phase (e.g., one worktree per sub-task, cleaned up after fan-in) and treat any observed race as a priority fix — this mechanism is reused by every future implementation task, so its correctness compounds in importance.

## Future Improvements

- `max_parallel_impl_agents` capping by repo scale (§F.2) — Phase 10.
- Richer self-check (actual test execution per sub-task, not just parse/import checks) — Phase 07 QA agents build on top of this, but a stronger CodeGen-level self-check is a reasonable later enhancement.

## Research Opportunities

Compare CodeGen output quality/first-pass-acceptance rate between Fast and High-capability tiers on the same sub-task types, once enough real runs exist — directly informs whether the Implementation Manager's tier-assignment heuristic (task 1's per-sub-task input) needs revision ahead of Phase 10's formalization.
