# Section 01 — MCP Client Base, Idempotency & GitHub Integration

## Objective

Implement the shared MCP client base and idempotency layer (§J.2/§J.3), then swap Phase 08's `LocalGitAdapter` for the official GitHub MCP server as a drop-in `GitProviderAdapter` implementation.

## Why It Exists

Every future MCP integration (Jira, Slack, and any custom adapter) shares the same idempotency-key requirement (§J.3: duplicate triggers from retries/resumed checkpoints must not produce duplicate side effects). Building this once, and proving GitHub MCP is a true drop-in replacement for Phase 08's adapter, validates the whole `GitProviderAdapter` seam.

## Dependencies

Phase 08 §04 (`GitProviderAdapter` interface, `LocalGitAdapter` implementation and its idempotency test to reuse).

## Atomic Implementation Tasks

1. Implement `packages/mcp_integrations/base.py`'s shared MCP client wrapper and `idempotency.py`'s idempotency-key store (reusing Postgres, per §J.3).
2. Implement `GitHubMCPAdapter` conforming to Phase 08's `GitProviderAdapter` Protocol, using the `mcp` Python SDK against the official GitHub MCP server.
3. Re-run Phase 08 §04's exact PR-creation and retry/idempotency tests against `GitHubMCPAdapter` unmodified, confirming the swap required zero changes to any calling code.
4. Swap the active adapter in configuration and re-run the Phase 08 end-to-end demo against a real GitHub repo.

## Manual Testing Procedure

Run the Phase 08 demo feature through to a real GitHub PR; force a retry and confirm no duplicate PR; confirm the swap from `LocalGitAdapter` required no changes outside adapter configuration.

## Expected Demo

A real GitHub PR link created by the platform, plus confirmation the adapter swap was config-only (grep-verifiable: zero changes to `packages/agents/release/`).

## Acceptance Criteria

- [ ] `GitHubMCPAdapter` passes Phase 08's exact `GitProviderAdapter` test suite unmodified.
- [ ] The adapter swap required zero changes to calling code outside adapter registration/config.
- [ ] Idempotency holds under a real forced retry against the live GitHub API.

## Risks

MCP server maturity moves fast (blueprint's own caveat, §J.1) — re-verify GitHub MCP's current capabilities against live docs before this section, not from memory.

## Future Improvements

GitLab MCP evaluation, Azure DevOps custom adapter — build only if actually needed by a real target environment.
