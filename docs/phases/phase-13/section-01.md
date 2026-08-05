# Section 01 — Security QA: Semgrep Inline + CodeQL Deep Scans

## Objective

Wire Security SAST (Semgrep, inline, risk≥Medium) and Security Deep (CodeQL, dataflow, risk≥High + periodic) per §K.1, and connect `FL-08` (critical security finding → design phase, HITL, registered but dormant since Phase 10 §04) to a real trigger for the first time.

## Why It Exists

Phase 06's Security Architect used Semgrep for existing-pattern matching during design; this section adds it as an inline QA gate on the actual diff, plus CodeQL's deeper dataflow analysis, which catches classes of issues pattern-matching structurally cannot (per the blueprint's own comparative analysis, §G.3).

## Dependencies

Phase 07 (QA pipeline), Phase 10 (real risk tiers), Phase 10 §04 (`FL-08` registry entry).

## Atomic Implementation Tasks

1. Wire Semgrep as an inline QA Manager check, active when `risk_tier >= Medium`.
2. Wire CodeQL as a periodic/async deep scan, active when `risk_tier >= High`, running outside the task's critical path (results attached when ready, not blocking).
3. Wire a critical Semgrep/CodeQL finding to fire `FL-08` (design phase, HITL).
4. Test with a seeded vulnerability (e.g., a SQL injection pattern) at High risk tier and confirm both tools flag it and `FL-08` fires correctly.

## Manual Testing Procedure

Seed a known vulnerability into a demo change at High risk tier; confirm Semgrep flags it inline and CodeQL's async scan corroborates; confirm `FL-08` fires with HITL.

## Expected Demo

Terminal walkthrough of the seeded-vulnerability case showing both tools' findings and the `FL-08` escalation.

## Acceptance Criteria

- [ ] Semgrep/CodeQL activation correctly follows §K.1's risk-tier gating.
- [ ] Security scan catches the seeded-vulnerability benchmark — the blueprint's stated Phase 13 target.
- [ ] `FL-08` fires correctly on a critical finding.

## Risks

CodeQL scan latency could bottleneck if run synchronously — mitigated by running it async, attaching results when ready rather than blocking QA completion.

## Future Improvements

Expand the seeded-vulnerability benchmark set over time as real findings accumulate.
