# Section 06 — Sufficiency Gate, B.4 Function, CLI, and Benchmarks

## Objective

Stop the loop with §E.4's **3-way exit shape**, driven by a Phase-04 `RequirementsSufficiency` score that does not impute missing §B.4 signals. Implement `compute_confidence()` **exactly** per §B.4 as a pure function for later phases. Ship the CLI demo and a small engine benchmark.

## Why It Exists

Literal section-04 fed `compute_confidence()` with placeholders for `precedent_strength` and `validator_agreement`. That violates §B.4 Fail-Closed ("if any input is unavailable, do not impute"). Phase 04 has no episodic memory and no `Validator`(requirements) — those are Phase 05/06+. Using 0.0 or 1.0 as stand-ins would either never exit or falsely clear the 0.80 floor.

Keep the platform formula. Change **what the requirements loop uses to stop**.

## Expected Architecture

### `packages/common/confidence.py`

```python
def compute_confidence(
    retrieval_coverage: float,
    precedent_strength: float,
    validator_agreement: float,
    static_check_cleanliness: float,
) -> float:
    ...
```

Weights 0.35 / 0.20 / 0.30 / 0.15. Each signal must be in `[0, 1]`. If any signal is `None` / missing, **raise** a distinct error. Callers treat that as below floor. Comment that weights are v1 pending Phase 15. Unit-test in isolation with synthetic inputs. Phase 04's engine **does not call this** to decide exit.

### `RequirementsSufficiency` (`sufficiency.py`)

Signals that actually exist now:

- all `mandatory` activated slots answered (human or accepted auto-answer)
- no unresolved `CONTRADICTION`
- high-impact UNKNOWNs remaining (count)
- `evidence_coverage`: fraction of activated slots that had an evidence plan and received evidence **or** an explicit UNKNOWN (honest miss)
- human `accept_gaps` flag
- no remaining askable slot **or** human-question budget exhausted

3-way exit (§E.4 shape):

1. **spec_ready** — mandatory answered, zero contradictions, high-impact UNKNOWN count = 0 (or only logged assumptions the policy allows).
2. **accept_gaps** — engineer explicitly accepts remaining open assumptions (CLI confirm); they go to `RequirementsSpec.assumptions` / `open_ambiguities`.
3. **needs_hitl** — cannot raise sufficiency further (budget exhausted, extract failed, RI stale/unavailable, stuck contradictions). Phase 04 **returns this result**; it does not call `interrupt()`.

If RI is missing/stale, (1) cannot fire.

### Engine orchestrator (`engine.py`)

`step()` / `run()`:

extract (once) → snapshot (once) → classify → activate slots → execute due EvidencePlans → auto-answer → sufficiency check → else rank and yield one human question.

CLI (`scripts/demo_requirements_engine.py`) scripts the three README scenarios. Well-specified answers can be canned; vague can be interactive or fixture-scripted.

### Observability

Append-only `SessionTrace`: claims, snapshot id/hash, each RI call (method, cache, cost), auto-answers, questions, statuses, exit reason. This is Screen 2's data shape and Phase 15's silver labels. Optional `TelemetrySink` spans (`tool_call` for RI, `llm_call` already from the adapter).

### Benchmarks (`tests/integration/test_requirements_engine.py` + counters)

Not retrieval fusion. Measure, on the Phase 03 corpus:

| Scenario | LLM calls | Distinct RI calls | Semantic calls | Human questions |
|---|---|---|---|---|
| Well-specified feature | 1 | snapshot + few targeted | 0 | 0–2 |
| Vague one-liner | 1 | snapshot + targeted | 0–2 | 6–10 |
| Security / PII | 1 | snapshot + auth lexical/graph | 0–1 | Qsec still asked |

Assert auto-answer **correctness** on a small labeled set (e.g. "auth service exists" = true on the corpus; "business objective" not auto-answered). Do not pretend RI is perfect: if lexical is skipped for missing Zoekt, the test must skip or assert fail-closed, not invent JWT absence.

## Dependencies

Sections 01–05. Phase 03 corpus. Phase 02 adapter (tests may fake it).

## Atomic Implementation Tasks

1. `compute_confidence()` + fail-closed tests (including missing signal).
2. `RequirementsSufficiency` + three exit tests against synthetic sessions.
3. `engine.py` wiring; `project.py` at exit.
4. CLI three-scenario demo.
5. Integration tests: well-specified exits `spec_ready` with few/no questions; vague does not dump the whole bank; security activates `Qsec*`; stale index → `needs_hitl` / error, not a spec.
6. Counter assertions (LLM = 1 on the happy extract path; semantic not used for stack slots).
7. Register `requirements_engine` in `pyproject.toml` package list when code lands.

## Manual Testing Procedure

1. Run all three CLI scenarios; read the exit reason and spec.
2. Confirm printed confidence **formula** is not a fake 0.80 from placeholders — print sufficiency fields instead; print `compute_confidence` only in its unit tests.
3. Kill-and-rerun is **not** required here (Phase 05 crash/resume).

## Expected Demo

Three CLI traces, each ending with `RequirementsSpec` JSON, sufficiency breakdown, RI/LLM counters, and the exit condition by name.

## Acceptance Criteria

- [ ] `compute_confidence()` matches §B.4 and fail-closes on missing inputs; engine exit does not call it with placeholders.
- [ ] All three §E.4 exit conditions are independently reachable in tests.
- [ ] Demo scenarios exit for explainable reasons.
- [ ] Auto-answer evidence is in the trace.
- [ ] Benchmark counters show the evidence-first path is cheaper than one RI+LLM round per slot.

## Risks

- **Risk:** Sufficiency is too loose and ships thin specs. **Mitigation:** mandatory slots + contradiction block; Phase 05 `Validator`(requirements) is the independent check.
- **Risk:** Confusing sufficiency with §B.4 in later phases. **Mitigation:** names, comments, Phase 05 section-05 pointer (Confidence Scorer is the first honest `compute_confidence` caller).

## Future Improvements

- Phase 05 Confidence Scorer: derive `retrieval_coverage` from `evidence_coverage` / auto-answer stats; other signals from Validator + (later) episodic memory. Until a signal exists, scorer fail-closes rather than inventing 0.5.
- Phase 15: logistic recalibration of B.4 weights.

## Research Opportunities

Once traces exist, compare sufficiency-only exit vs waiting for a real B.4 score on the same sessions — do not merge the two scores now.
