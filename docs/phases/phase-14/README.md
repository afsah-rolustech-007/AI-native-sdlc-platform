# Phase 14 — MCP & External Integrations

## Goal

Replace Phase 08's thin `LocalGitAdapter` with the official GitHub MCP server, add Jira and Slack integrations, and establish the adapter pattern for any service without a mature MCP server — connecting the platform to a real engineering ecosystem end to end.

## Why This Phase Exists

Phase 08 proved the PR/deployment flow works against a minimal local adapter, deliberately deferring real provider integration. This phase swaps that adapter for the real thing, proving (like Phase 02's model swap and Phase 11's graph-DB swap) that the seam was drawn correctly.

## Dependencies

Phase 08 (`GitProviderAdapter` interface to implement against).

## Expected Live Demo

Run a task end to end starting from a real Jira ticket import (no manual data re-entry), through to a real GitHub PR, with Slack notifying a human at each HITL checkpoint instead of relying on the UI alone.

## Deliverables

- `packages/mcp_integrations/clients/github.py`, `jira.py`, `slack.py`.
- Idempotency layer (§J.3) applied uniformly across all MCP calls.
- Adapter-pattern template for any future service lacking a mature MCP server.

## Sections

1. [MCP Client Base, Idempotency & GitHub Integration](section-01.md)
2. [Jira Ticket Import & Slack HITL Notifications](section-02.md)
