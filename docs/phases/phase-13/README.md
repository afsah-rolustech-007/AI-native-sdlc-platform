# Phase 13 — Advanced QA

## Goal

Layer in the risk-gated QA checks from §K.1 that Phase 07 deliberately deferred: security (Semgrep inline + CodeQL deep), mutation testing, property-based testing, performance, accessibility, API contract fuzzing — plus regression-test generation (§K.4) and the full evidence bundle standard (§K.5). Phase 07's "Always" checks remain unchanged; this phase activates the "risk ≥ X" rows now that Phase 10 provides real risk tiers to gate on.

## Why This Phase Exists

Building the full QA matrix in Phase 07 would have meant gating checks against risk tiers that didn't exist yet. Now that Phase 10 provides real routing, §F.4's agent-selection rules (Security QA/Performance QA/Exploratory for risk≥High, Mutation Testing for critical-path modules, etc.) can be wired to real conditions instead of stubs.

## Dependencies

Phase 07 (QA pipeline to extend), Phase 10 (real risk tiers to gate on).

## Expected Live Demo

Run the same task at two different (real) risk tiers and show the QA plan differs: Low risk skips mutation/exploratory/performance; High risk activates Security SAST+Deep, Performance QA, and Exploratory Testing. Show a seeded vulnerability caught by Semgrep/CodeQL, and a regression test auto-generated and committed after a bug fix.

## Deliverables

- `packages/qa/security_qa.py` (Semgrep inline + CodeQL periodic), `mutation_runner.py`, `property_tester.py`.
- k6/Locust, axe-core, schemathesis integrations, risk-gated.
- Regression test generation (§K.4) and evidence bundle standard (§K.5) fully wired.

## Sections

1. [Security QA: Semgrep Inline + CodeQL Deep Scans](section-01.md)
2. [Mutation, Property-Based, Performance & Accessibility QA](section-02.md)
3. [Regression Test Generation & Full Evidence Bundle](section-03.md)
