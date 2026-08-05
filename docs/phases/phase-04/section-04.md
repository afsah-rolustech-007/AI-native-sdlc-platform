# Section 04 — Confidence Model & Gated Exit Conditions

## Objective

Implement the composite Confidence Model formula (§B.4) as a standalone, pure, unit-tested function, and implement the Requirements Engine's 3-way exit condition (§E.4) on top of it — the mechanism that decides when the questioning loop stops.

## Why It Exists

Confidence is, per the blueprint, "a load-bearing gate" used across the entire platform (requirements exit, design escalation, auto-merge eligibility). Building the formula once, here, as a pure function with no agent/graph dependency, means every later consumer (Phase 05's Confidence Scorer agent, Phase 10's routing rules) calls the same tested implementation rather than each re-deriving it.

## Expected Architecture

`packages/common/confidence.py` implements:

```python
def compute_confidence(
    retrieval_coverage: float,
    precedent_strength: float,
    validator_agreement: float,
    static_check_cleanliness: float,
) -> float:
    ...  # 0.35/0.20/0.30/0.15 weighted sum, per §B.4
```

At this phase, `precedent_strength` and `validator_agreement` have no real data source yet (no episodic memory, no validators exist until Phase 05/06) — the function itself must still be complete and correct; callers at this phase pass conservative placeholder inputs (documented as such) or the function is tested purely in isolation with synthetic inputs, deferring real end-to-end confidence computation to Phase 05. `packages/requirements_engine/exit.py` implements the 3-way exit evaluator per §E.4, calling `compute_confidence` and checking against the phase floor (0.80, §B.4's table).

## Dependencies

None additional beyond Sections 01–03 (needs a session's retrieval-coverage signal from the auto-answer step to feed the formula).

## Atomic Implementation Tasks

1. Implement `compute_confidence()` exactly per §B.4's formula and weights, with input validation (each signal in `[0,1]`).
2. Implement Fail-Closed behavior explicitly: wrap the computation so that if any required signal is missing/unavailable, the function does not impute a default — it raises a distinguishable exception, and callers must treat that as "below floor," never as "assume high confidence" (§B.4's explicit rule, unit-tested here as a first-class case, mirroring Phase 00 Section 03's budget-check fail-closed pattern).
3. Derive `retrieval_coverage` for a requirements session as a function of Section 03's auto-answer results (e.g., fraction of auto-answerable questions successfully resolved, or a similar defensible proxy) — document the exact derivation since it's a genuine design decision the blueprint doesn't fully specify at this granularity.
4. Implement the 3-way exit evaluator (§E.4): (a) confidence ≥ 0.80 AND all mandatory questions answered → exit; (b) human explicitly accepts remaining open assumptions → exit, logging them for the Phase Handoff Packet (built properly in Phase 12, but the `open_assumptions` list itself starts being populated here); (c) confidence cannot be raised further → signal for HITL (the actual `interrupt()` wiring is Phase 05 — this phase's exit evaluator just returns a clear "needs HITL" result).
5. Unit tests: formula produces expected output for known input combinations (including the ablation-relevant case of correlated signals, noted in §B.4 as a future recalibration concern — not solved now, just not broken by it); fail-closed behavior triggers "below floor" on a missing-signal simulation; all three exit conditions are independently testable against synthetic session states.

## Manual Testing Procedure

1. Run the three demo scenarios end-to-end (question queue + auto-answer + confidence + exit evaluation) and observe which exit condition fires for each: the well-specified scenario should hit condition (a) quickly; the vague scenario should require several rounds and may hit condition (b) or (c) depending on how the demo script scripts human answers.
2. Manually verify the printed confidence score at each round is plausible given the mix of auto-answered vs. human-answered vs. still-open questions.

## Expected Demo

CLI output for each of the three scenarios showing the confidence score after each answered question, converging (or not) toward the 0.80 floor, ending with the exit condition that fired printed explicitly.

## Acceptance Criteria

- [ ] `compute_confidence()` matches §B.4's formula and weights exactly, and is unit-tested independent of any session/engine context.
- [ ] A simulated missing/failed signal results in "below floor," never an imputed passing score — this is directly tested, not just asserted in a docstring.
- [ ] All three exit conditions from §E.4 are independently reachable and tested against synthetic scenarios.
- [ ] The three demo scenarios from the Phase 04 README each exit via a plausible, explainable condition.

## Risks

- **Risk:** The v1 weights (§B.4) are stated as starter values pending shadow-mode recalibration (§L.5) — using them uncritically here is correct *for now*, but it would be a mistake to treat them as validated. **Mitigation:** explicitly note in code comments that these weights are provisional and named for future recalibration (Phase 15), so nobody mistakes them for tuned constants later.

## Future Improvements

- Logistic-regression recalibration of the weights against real task outcomes, with a drop-one ablation for `retrieval_coverage`/`validator_agreement` correlation — Phase 15 (§L.3/§L.5), requires real outcome data that doesn't exist until Phase 05+.

## Research Opportunities

This is one of the roadmap's clearest research hooks: once Phase 15's golden dataset exists, revisit whether all four signals are actually independent contributors, or whether the formula should be simplified/reweighted. Treat the current formula as baseline v1, not ground truth.
