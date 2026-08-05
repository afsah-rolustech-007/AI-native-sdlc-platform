# Phase 09 — Minimal UI

## Goal

Make the entire system, built and proven via CLI/API/Postgres inspection through Phases 00–08, legible to a human through a real browser UI — 12 screens (§P) as a thin read layer over objects that already exist. By the end of this phase, a human can answer "what is running, why, and what does it need from me" without touching a terminal.

## Why This Phase Exists

Every prior phase has been verified by an engineer comfortable reading trace logs and querying Postgres directly. That's fine for building the platform, but the platform's actual purpose involves a human (developer/reviewer/deployer) interacting with it regularly — and per the brief, "backend research is the priority," so this phase is intentionally scoped as thin as the backend allows, not as a product-polish exercise. It's sequenced after Phase 08 specifically because most screens (Approval Requests, QA Summary, Deployment Status, Final Report) have no real data to render before real HITL/QA/release data exists.

## Dependencies

Phase 08 (real agents, HITL events, QA evidence, deployment records — everything the UI reads).

## High-Level Architecture

```
React + Vite + TS SPA
        │
        ├── REST client (typed, from FastAPI's OpenAPI schema) ── reads Task/QAEvidence/
        │                                                          DeploymentRecord/etc.
        │
        └── useWebSocket hook ── subscribes to AgentEvent stream (§P's WebSocket protocol)
                                   for live updates (agent_started, hitl_required, etc.)

FastAPI (apps/api/)
        ├── REST endpoints: read existing Task/approval/QA/deployment records
        ├── WebSocket endpoint: broadcasts AgentEvent as nodes emit them (extends
        │                       Phase 00 §05's emit_node_event to also push over WS)
        └── Write endpoints: submit new Task (Screen 1), respond to HITL (Screens 2/7/8)
```

No new backend data model is introduced by this phase (§P's explicit constraint) — every screen is a view over a table/object that already exists from Phases 00–08.

## Expected Live Demo

Open the UI in a browser. Submit a new task via Screen 1. Watch Screen 2 render the live requirements interview, including auto-answered questions with their evidence shown. Watch Screen 3/4 show the (still fail-closed-default) workflow profile and current SDLC phase position. Watch Screen 5/6 show agents executing live via the WebSocket stream. Respond to a real approval request on Screen 8, using the evidence bundle from Phase 08 §02. Watch the task complete and view its Final Report (Screen 12).

## Deliverables

- `ui/` — Vite + React + TS + Tailwind + shadcn/ui project.
- FastAPI REST endpoints backing all 12 screens' data needs.
- WebSocket endpoint broadcasting `AgentEvent` (§P schema).
- `useWebSocket`, `useTask`, `useHITL` hooks.

## Sections

1. [Frontend Scaffold, API Client & WebSocket Hook](section-01.md)
2. [Task Intake & Requirement Interview Screens (1, 2)](section-02.md)
3. [Workflow Overview & SDLC Phase View (3, 4)](section-03.md)
4. [Live Execution: Active Agents, Timeline & Agent Logs (5, 6, 9)](section-04.md)
5. [HITL: Questions Queue & Approval Requests (7, 8)](section-05.md)
6. [QA Summary, Deployment Status & Final Report (10, 11, 12)](section-06.md)
