# Section 02 — Task Intake & Requirement Interview Screens (1, 2)

## Objective

Build Screen 1 (New Task — intake form) and Screen 2 (Requirement Interview — current question from the Questioning Engine, plus auto-answered questions with retrieved evidence shown), per §P.

## Why It Exists

These are the first screens a user actually interacts with, and Screen 2 is where the platform's core differentiator (Phase 04's auto-answer-from-repo transparency) becomes visible to a human for the first time, rather than just visible in a CLI trace.

## Expected Architecture

Screen 1 is a simple form (free text + optional structured fields per §P) posting to a `POST /tasks` endpoint that constructs a `Task` (Phase 00) and kicks off the graph (Phase 01/05). Screen 2 polls/subscribes (via Section 01's `useWebSocket` plus a REST fetch of current `hitl_queue`/session state) to render the current pending question, and a running list of already-answered questions — visually distinguishing auto-answered (with evidence link) from human-answered ones, per §P's explicit requirement.

## Dependencies

Section 01 (API client, WebSocket hook), Phase 05 (real requirements sessions to render).

## Atomic Implementation Tasks

1. Implement the `POST /tasks` FastAPI endpoint and Screen 1's form, wired to it.
2. Implement a `GET /tasks/{id}/requirements-session` endpoint returning current question + full answered-question history with auto-answer evidence.
3. Build Screen 2's UI: current question prompt with an answer input, a scrolling history of prior Q&A entries, auto-answered entries visually distinct (e.g., a badge + expandable evidence panel) per §P.
4. Wire Screen 2's answer submission to resume the paused graph (via a `POST /tasks/{id}/respond` endpoint calling Phase 01/05's resume mechanism).
5. Wire live updates via `useWebSocket` so a new question appears without a manual page refresh.
6. Integration test: submit a task via Screen 1, walk through a real requirements session via Screen 2 in the browser, confirm auto-answered questions display their evidence correctly.

## Manual Testing Procedure

1. Submit both demo scenarios (well-specified, vague — from Phase 04) via Screen 1.
2. Walk through Screen 2 for each, confirming the auto-answer/human-answer distinction renders correctly and evidence is inspectable.
3. Confirm the session correctly resumes after answering, with the next question appearing live.

## Expected Demo

Screen recording of submitting a task via Screen 1 and completing a full requirements interview via Screen 2, with at least one auto-answered question's evidence expanded and shown.

## Acceptance Criteria

- [ ] Screen 1 successfully creates a real `Task` and starts the graph.
- [ ] Screen 2 correctly renders live questions, and visually distinguishes auto-answered (with evidence) from human-answered questions per §P.
- [ ] Answer submission correctly resumes the paused graph via a real interrupt/resume round-trip through the UI (not just via the CLI resume script from Phase 01/05).

## Risks

- **Risk:** UI polling/WebSocket timing mismatches could show a stale "current question" briefly. **Mitigation:** treat the REST fetch as ground truth on load/reconnect (per Section 01's risk mitigation) and the WebSocket as an incremental update layer.

## Future Improvements

- Structured intake fields (beyond free text) for Screen 1 — a reasonable enhancement once real usage patterns suggest which fields are commonly needed.

## Research Opportunities

None.
