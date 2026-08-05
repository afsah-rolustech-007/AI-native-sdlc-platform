# Section 02 — Jira Ticket Import & Slack HITL Notifications

## Objective

Implement Jira ticket import (`source=ticket_import`, §B.1) via the Atlassian official remote MCP server, and Slack notifications for HITL events (§J.1: "primary channel for HITL notifications"), reducing reliance on manually polling the Phase 09 UI.

## Why It Exists

This closes the "no manual data re-entry" gap explicitly named as Phase 14's completion criterion (§C's table), and makes HITL genuinely responsive for a human who isn't watching the UI continuously — a real usability requirement, not just an integration checkbox.

## Dependencies

Phase 00 (`Task.source` field), Phase 08 §01 (`hitl_log` events to notify on).

## Atomic Implementation Tasks

1. Implement `JiraMCPAdapter` mapping a Jira ticket to a `Task` (`source=ticket_import`), populating title/description from ticket fields.
2. Implement `SlackMCPAdapter` sending a notification on every `hitl_required` event (Phase 09 §01's event stream), with a link back to the relevant UI screen (7 or 8).
3. Test: import a real Jira ticket end to end into a running task; confirm a Slack message arrives at the first HITL checkpoint with a working link.

## Manual Testing Procedure

Create a test Jira ticket, import it, and walk the resulting task to its first approval gate; confirm Slack notification arrives and its link correctly opens the pending request in the UI.

## Expected Demo

This section's demo *is* Phase 14's overall live demo (see README): Jira ticket → task creation → Slack-notified HITL checkpoint → GitHub PR, no manual data re-entry at any step.

## Acceptance Criteria

- [ ] Jira ticket import correctly populates a `Task` with no manual re-entry of ticket content.
- [ ] Every `hitl_required` event triggers a Slack notification with a working link.

## Risks

Slack notification volume could become noisy at higher task throughput — acceptable at current scale; revisit filtering/batching only if it becomes a real usability complaint.

## Future Improvements

Notification batching/digest mode if volume becomes an issue.
