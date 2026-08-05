# Section 04 — Live Execution: Active Agents, Timeline & Agent Logs (5, 6, 9)

## Objective

Build Screen 5 (Active Agents — which agents are running now and their current tool call), Screen 6 (Live Execution Timeline — phase transitions, feedback loops, approvals, chronological), and Screen 9 (Agent Logs — raw OTel trace detail per agent).

## Why It Exists

These three screens are the primary window into "what is the platform doing right now and why" — the core legibility goal the whole phase serves. They share a common data source (the OTel/`agent_events` trail built since Phase 00) and are grouped into one section because they're three views over the same underlying event stream at different granularities (live/summary/raw).

## Expected Architecture

Screen 5 subscribes to `agent_started`/`agent_tool_call`/`agent_completed`/`agent_failed` events (§P's `AgentEvent.event_type` enum) via Section 01's WebSocket hook, maintaining a "currently active agents" derived state (an agent is active between its `agent_started` and `agent_completed`/`agent_failed` events). Screen 6 renders the full chronological `agent_events` stream for a task as a timeline, with `masc_flag`, `hitl_required`, `rollback_initiated`, `feedback_loop_triggered` events visually flagged distinctly. Screen 9 provides a raw, filterable/searchable view of the full OTel trace detail (reads directly from the trace backend/Langfuse if exposed via API, or from the same `agent_events` data at full fidelity).

## Dependencies

Section 01 (WebSocket plumbing), Phase 05–08 (real, varied agent activity including feedback loops and HITL events to render meaningfully).

## Atomic Implementation Tasks

1. Implement `GET /tasks/{id}/events` (full historical event list) and ensure the WebSocket stream (Section 01) delivers the same shape for live updates.
2. Build Screen 5: derive "currently active" agents from the event stream and render their current tool call/status.
3. Build Screen 6: chronological timeline component, with distinct visual treatment for `masc_flag`, `hitl_required`, `rollback_initiated`, `feedback_loop_triggered` event types.
4. Build Screen 9: a searchable/filterable raw log view (by agent, by phase, by event type) — deliberately the "escape hatch" screen for when the higher-level views (5, 6) don't have enough detail.
5. Integration test: run a task with a forced feedback loop and a forced MASC flag, and confirm both Screen 6's timeline and Screen 9's raw log correctly surface these events distinctly.

## Manual Testing Procedure

1. Run a task with parallel CodeGen sub-agents (Phase 06 §05) and confirm Screen 5 shows multiple agents active simultaneously — a direct visual proof of the fan-out concurrency built in Phase 06.
2. Run a task with a forced validator failure/feedback loop and confirm Screen 6 clearly flags it in the timeline.
3. Use Screen 9 to filter down to just one agent's raw trace and confirm the detail is complete and accurate against the underlying OTel data.

## Expected Demo

Screen recording showing Screen 5 with multiple agents active concurrently during a Phase 06 parallel fan-out demo, followed by Screen 6's timeline view of the same task highlighting a feedback loop event, followed by Screen 9 drilling into the raw trace for one specific agent.

## Acceptance Criteria

- [ ] Screen 5 correctly shows multiple genuinely concurrent agents when a real parallel fan-out is running (verified against Phase 06's trace-timing proof).
- [ ] Screen 6's timeline correctly and distinctly flags MASC flags, HITL requirements, rollbacks, and feedback loops.
- [ ] Screen 9 provides complete, accurate raw trace detail, filterable by agent/phase/event type.

## Risks

- **Risk:** A high-volume task (many parallel agents, many tool calls) could overwhelm Screen 6/9's rendering if not paginated/virtualized. **Mitigation:** not a pressing concern at MVP task volumes, but worth a note — if scroll performance becomes an issue, standard list-virtualization is the fix, deferred until it's actually observed as a problem.

## Future Improvements

- Deeper Langfuse embedding/linking for token-cost-per-agent visualization directly in Screen 9 — a reasonable enhancement once Langfuse is consistently running (per `techstack.md`'s recommendation from Phase 00).

## Research Opportunities

None.
