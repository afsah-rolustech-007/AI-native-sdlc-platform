# Section 01 — QA Manager & Risk-Scoped QA Plan

## Objective

Implement the QA Manager (§E.8): computes QA depth from risk tier and dispatches sub-agents, replacing Phase 01's stub `qa_node` with the entry point for the real QA pipeline.

## Why It Exists

QA depth must scale with risk — running exhaustive QA on a trivial Low-risk change wastes budget; running only cursory QA on a Critical-risk change is dangerous. The QA Manager is where this decision is made and enacted, even though (per `roadmap.md` §2.4) it uses the fail-closed default profile until Phase 10's real `resolve_workflow_profile()` exists — meaning it should currently run standard-depth QA for everything, with the *structure* for risk-based variation already in place.

## Expected Architecture

`packages/agents/qa/qa_manager.py`'s `QAManager(BaseAgent)` (Fast tier, §E.8) reads the current (still-conservative-default) QA depth setting, builds an ordered QA plan referencing §K.1's activation matrix (at this phase, only the "Always" rows are wired: static analysis, secrets scanning, dependency vulnerability, unit/integration tests, spec QA — risk-gated rows like Security SAST/Deep, mutation testing, exploratory testing are Phase 13's addition), and dispatches sub-agents accordingly. On any sub-agent critical failure, routes back to Implementation per §D.3.

## Dependencies

Phase 06 (a merged diff to QA), Phase 03 (dependency graph for Section 02).

## Atomic Implementation Tasks

1. Implement the QA plan data structure (which checks are active, in what order) — parametrized by a QA-depth setting even though only one depth (`standard`, the fail-closed default) is currently reachable.
2. Wire the "Always" rows of §K.1's matrix that are already available from prior phases: static analysis and secrets/dependency scanning reuse Phase 06 §07's tool integrations (extend `Validator`(implementation)'s tool set or call the same underlying functions from the QA Manager — avoid duplicating the ruff/ mypy /Semgrep wiring).
3. Implement critical-failure routing: any QA sub-agent reporting a critical failure routes the task back to `TaskState.IMPLEMENTATION` per §D.3's `QA — spec compliance fail` row (`FL-06`, max 3×, same phase).
4. Wire the real `qa` graph node, replacing Phase 01's stub, dispatching QA Manager first.
5. Integration test: the demo feature runs through the full QA plan and produces a `QAEvidence` (§B.2) record with all "Always" checks populated.

## Manual Testing Procedure

1. Run the demo feature through QA and print the resulting `QAEvidence`.
2. Confirm all "Always" checks from §K.1 ran and their results are populated (not stubbed with placeholder pass values).
3. Force a critical failure (e.g., a deliberately broken diff) and confirm routing back to Implementation.

## Expected Demo

Terminal output of a complete `QAEvidence` record for the demo feature, followed by a forced-failure run showing the correct routing back to Implementation with a structured `FeedbackReport`.

## Acceptance Criteria

- [ ] QA Manager correctly dispatches all "Always" rows of §K.1's activation matrix.
- [ ] `QAEvidence` is fully and correctly populated for a real QA run.
- [ ] Critical failure correctly routes back to Implementation (`FL-06`) with a specific, structured report.
- [ ] The real `qa` node replaces Phase 01's stub.

## Risks

- **Risk:** Building QA depth logic against a single (default) risk tier now risks the eventual Phase 10 integration requiring rework. **Mitigation:** structure the QA plan as data-driven from a `qa_depth` enum value from day one (even if only one value is ever passed in currently) — Phase 10 then only needs to supply a different, correctly-computed `qa_depth`, not restructure this section's code.

## Future Improvements

- Full risk-tiered QA activation (Security SAST/Deep, mutation testing, exploratory testing, performance, accessibility) — Phase 13, gated correctly once Phase 10's real risk tiers exist.

## Research Opportunities

None yet — becomes relevant once Phase 15's QA KPIs (defect detection rate, false positive rate, §L.2) exist to evaluate plan effectiveness against.
