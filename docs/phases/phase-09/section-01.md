# Section 01 — Frontend Scaffold, API Client & WebSocket Hook

## Objective

Stand up the Vite + React + TypeScript + Tailwind + shadcn/ui project, a typed REST client generated/derived from FastAPI's OpenAPI schema, and the `useWebSocket` hook that consumes the `AgentEvent` stream (§P) — the shared plumbing every one of the 12 screens builds on.

## Why It Exists

Getting the typed-client and realtime-event plumbing right once, before any screen is built, means every subsequent section (02–06) is purely screen-specific work, not re-solving "how do I talk to the backend" five more times.

## Expected Architecture

`ui/` is a Vite + React + TS project per `techstack.md` §4. A typed API client is generated from FastAPI's auto-exposed OpenAPI schema (via `openapi-typescript` or equivalent) and wrapped with a thin `apiClient` using `fetch` + TanStack Query for caching/refetch. `useWebSocket(taskId)` opens a WebSocket connection to the FastAPI backend's event endpoint, parses incoming `AgentEvent` (§P's exact TypedDict, mirrored as a TS type) messages, and exposes them as a reactive event stream (e.g., a Zustand store or React context, kept intentionally simple per the brief's "thin" instruction).

## Dependencies

Phase 00 (FastAPI skeleton), Phase 08 (real events to stream — though this section can be built/tested against synthetic events first).

## Atomic Implementation Tasks

1. Scaffold the Vite + React + TS project with Tailwind and shadcn/ui installed and configured.
2. Set up OpenAPI schema generation from the FastAPI app and a TS type-generation step (wired into the `Makefile`'s `dev` target so types stay fresh without manual regeneration).
3. Implement the `apiClient` wrapper with TanStack Query integration.
4. Implement the FastAPI WebSocket endpoint (`/ws/tasks/{task_id}`) that subscribes to Redis pub/sub (or the same bus the `telemetry_adapter` / `TelemetrySink` callback publishes `AgentEvent` onto). Do not have the UI read OTel exporters directly.
5. Implement the `useWebSocket(taskId)` hook: connects, parses `AgentEvent` messages, exposes them reactively, handles reconnection on drop.
6. Integration test: submit a synthetic event through the backend's pub/sub channel and confirm a connected browser client receives and correctly parses it.

## Manual Testing Procedure

1. Run `make dev` (API + worker + UI) and open the UI in a browser.
2. Trigger a synthetic backend event (e.g., a test script publishing to the pub/sub channel) and confirm the browser's dev console shows the event received via `useWebSocket`.
3. Kill and restart the API process; confirm the WebSocket client reconnects automatically.

## Expected Demo

Browser dev console (or a minimal debug screen) showing live `AgentEvent` messages arriving in real time as a synthetic or real task executes — the foundation every later screen's "live" feel depends on.

## Acceptance Criteria

- [ ] TypeScript types are generated from the backend's OpenAPI schema, not hand-duplicated.
- [ ] `useWebSocket` correctly receives, parses, and exposes `AgentEvent` messages, and reconnects after a dropped connection.
- [ ] The full `make dev` loop (API + worker + UI concurrently) works from a clean checkout, extending Phase 00 §06's rule to now include the UI.

## Risks

- **Risk:** WebSocket reconnection logic is easy to get subtly wrong (missed events during reconnect gap). **Mitigation:** on reconnect, have the client re-fetch current task state via REST (the source of truth) rather than assuming the WebSocket stream alone is authoritative — treat WS as a live-update convenience layer over a REST-fetched baseline, not the sole data source.

## Future Improvements

- None planned beyond what later sections need — kept intentionally minimal per the brief.

## Research Opportunities

None.
