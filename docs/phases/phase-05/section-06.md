# Section 06 — Intent Tracker

## Objective

Implement the Intent Tracker (§E.7) — the agent that classifies every new user message (including HITL responses) as `ADDITIVE | MODIFICATION | CONTRADICTION | IRRELEVANT` against the current `RequirementsSpec`, requiring explicit human confirmation before applying a `MODIFICATION`/`CONTRADICTION`.

## Why It Exists

Multi-round requirements sessions (Section 04) and, later, mid-implementation user messages (Phase 06+) create real opportunity for scope drift — a user casually mentioning a change that actually contradicts an already-approved requirement. Catching this at the point of utterance (rather than discovering it as a QA-phase spec-compliance failure, Phase 07) is significantly cheaper. This closes out Phase 05's full intake/planning agent roster per §E.8.

## Expected Architecture

`packages/orchestration/intent_tracker.py`'s `IntentTracker.classify(new_message, current_spec) -> IntentDiff` runs on every new inbound message (Fast tier model per §E.8's table) and produces a structured classification. `flag_drift_mid_implementation` is stubbed at this phase (no implementation exists yet to drift *during* — it becomes meaningfully testable in Phase 06) but its interface and the `ValidationFlag(flag_type="semantic_drift")` output shape are implemented now so Phase 06 wires into an already-defined contract. `intent_version` (§B.2) increments on every applied spec mutation.

## Dependencies

Section 04 (a `RequirementsSpec` to classify against), Section 01 (`BaseAgent`).

## Atomic Implementation Tasks

1. Implement `IntentDiff` schema (`classification`, `affected_requirement_ids`, `rationale`).
2. Implement `IntentTracker.classify()` as a `BaseAgent`-based Fast-tier classifier, run against every new message received during a requirements session (hook it into Section 04's node, before the message is otherwise processed).
3. Implement the `MODIFICATION`/`CONTRADICTION` confirmation gate: these classifications do not silently update `RequirementsSpec` — they must surface as an explicit human confirmation step (reuse `ApprovalGate`'s pattern conceptually, or a lighter-weight inline confirmation within the requirements interrupt flow — decide and document which).
4. Implement `intent_version` incrementing on every confirmed spec mutation, per §B.2.
5. Implement the `flag_drift_mid_implementation()` interface (returns `ValidationFlag | None`) with a clear docstring noting it becomes load-bearing in Phase 06 (feeding `FL-11`, §F.5).
6. Unit tests: a clearly additive message classifies correctly; a message directly contradicting an already-answered question classifies as `CONTRADICTION` and is blocked from silent application; an ambiguous message defaults to `MODIFICATION` (requiring confirmation) rather than guessing `ADDITIVE` — this is a small Fail-Closed-flavored judgment call worth stating explicitly and testing.

## Manual Testing Procedure

1. Run a requirements session (Section 04) and, mid-session, inject a message that clearly adds a new, unrelated requirement — confirm it's classified `ADDITIVE` and applied without extra friction.
2. Inject a message that reverses an earlier answer — confirm it's classified `MODIFICATION`/`CONTRADICTION` and requires explicit confirmation before `RequirementsSpec` changes.
3. Confirm `intent_version` increments only on confirmed mutations, not on every message.

## Expected Demo

Terminal output of a requirements session with three injected messages (additive, modification, irrelevant) showing the Intent Tracker's classification and, for the modification case, the confirmation step before the spec actually changes.

## Acceptance Criteria

- [ ] All four classification categories are reachable and correctly distinguished for representative example messages.
- [ ] `MODIFICATION`/`CONTRADICTION` never silently mutate `RequirementsSpec` — always require explicit confirmation, verified by a test that confirms the spec is unchanged until confirmation is given.
- [ ] `intent_version` increments correctly and only on confirmed mutations.
- [ ] `flag_drift_mid_implementation`'s interface is defined and stubbed, ready for Phase 06's real integration.

## Risks

- **Risk:** An ambiguous message being misclassified as `ADDITIVE` when it was actually a `CONTRADICTION` could silently corrupt the spec. **Mitigation:** the default-to-`MODIFICATION`-on-ambiguity rule (task 6) is the direct defense; treat any real-world misclassification discovered later as a prompt-tuning task, not a fundamental redesign.

## Future Improvements

- Fine-tuned Intent Classifier — explicitly named in §E.3 as a strong fine-tuning candidate ("high-volume, narrow-task agent with well-defined I/O") once enough labeled examples exist (Phase 15+).
- `flag_drift_mid_implementation` full activation — Phase 06.

## Research Opportunities

Once Phase 15's golden dataset includes labeled intent-classification examples, this is one of the clearer fine-tuning candidates in the entire roster (§E.3, justification #1) — worth prioritizing as an early fine-tuning experiment relative to other agents.
