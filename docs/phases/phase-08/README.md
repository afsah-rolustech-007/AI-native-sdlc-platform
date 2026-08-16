# Phase 08 — HITL & Release Governance

## Goal

Close the loop from validated QA evidence to a real, human-approved pull request — and from there to a real (or realistically simulated) deployment with mandatory approval and automated rollback on health failure. By the end of this phase, zero agent-authored commit reaches a protected branch without either explicit human approval or a passing, policy-defined auto-merge check.

## Why This Phase Exists

Everything built so far (Phases 05–07) produces increasingly trustworthy artifacts, but none of it has consequences outside the platform's own database yet. This phase is where the platform's actions become real — a real PR, a real (or CI/CD-simulated) deployment — which is exactly why Principle 4 (irreversible actions always require human approval) is enforced hardest here. It depends on Phase 01's interrupt/resume (the mechanism) and Phase 07's QA evidence (the content of what's being approved).

## Dependencies

Phase 01 (interrupt/resume mechanism), Phase 07 (QA evidence to build approval bundles from).

## High-Level Architecture

```
QAEvidence (pass/pass_with_warnings/fail)
        │
        ▼
  Review Manager ── coordinates diff review against design + standards
        │
        ▼
  ApprovalGate(pr) ── mandatory for Medium+ risk (fail-closed default: mandatory for all, until Phase 10)
        │
        ▼
  PR created via git provider adapter (real GitHub/GitLab call, or a thin
        │        local adapter simulating one if no live provider is configured yet)
        ▼
  Auto-merge check: risk=Low AND QA green AND confidence > AUTO_MERGE_CEILING
        │  (structurally present, but unreachable until Phase 10's real risk/confidence
        │   routing exists — until then, this path is always "requires human")
        ▼
  Release Manager ── coordinates deployment via existing CI/CD (never direct cloud API)
        │
        ▼
  ApprovalGate(deployment) ── ALWAYS fires for production, regardless of confidence
        │
        ▼
  Deployment ──▶ Monitoring Manager ── watches bake-in period
        │                                   │
        │                          incident? ──▶ NEW Task via lineage (never loops back)
        ▼
  Rollback Sub-agent ── on deployment health failure, executes rollback plan
```

## Expected Live Demo

Take a QA-passed task from Phase 07 through Review, `ApprovalGate`(pr), and PR creation against a real (or realistic local-adapter-simulated) git provider — showing the evidence bundle a human reviewer actually sees. Approve it; show the PR merges. Then simulate a deployment through the Release Manager, trigger `ApprovalGate`(deployment) (show it firing even when — hypothetically — confidence is high, proving Principle 4's "regardless of confidence" rule), approve it, and simulate a health-check failure post-deploy that triggers the Rollback Sub-agent automatically.

## Deliverables

- `packages/agents/release/review_manager.py`, `rollback_agent.py`, `monitoring_manager.py`.
- `ApprovalGate`(pr), `ApprovalGate`(deployment) instances.
- `packages/qa/evidence_collector.py` — evidence bundle generator (§K.5).
- Git provider adapter (thin, pre-Phase-14-MCP local version) for PR creation.
- Auto-merge policy check (structurally present, gated inert until Phase 10).

## Sections

1. [ApprovalGate Wiring at All Remaining Checkpoints](section-01.md)
2. [Evidence Bundle Generator](section-02.md)
3. [Review Manager](section-03.md)
4. [PR Creation & Auto-Merge Policy](section-04.md)
5. [Release Manager, Rollback Sub-agent & Monitoring Manager](section-05.md)
