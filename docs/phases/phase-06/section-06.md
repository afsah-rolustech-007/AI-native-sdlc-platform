# Section 06 — Fan-In (Wave Boundary), Demotion, Escalation & Integration Validator

## Objective

Implement the Fan-in Coordinator as the **formal per-wave boundary** (§D.4.1) — deterministic, zero LLM — including merge, demotion state machine (§D.4.4), pure plan amendment, WaveHandoffNote assembly (§D.10.6), and final Integration Validator (once).

## Why It Exists

Workers stay isolated. Fan-in is where intra-wave conflicts, cross-wave incompatibilities, discovered deps, and handoffs are resolved without a clever merge agent.

## Expected Architecture

After every branch in the **current wave** is terminal (`validated` | `blocked` | `failed`):

1. Select latest `merge_eligible` WCP/result (`demotion_ignore_keys` is the exclusion set; never rewrite `ImplementationResult.status`).
2. Intra-wave file overlap.
3. Intra-wave semantic conflict (§D.4.1.1).
4. Cross-wave check vs **prior** WaveHandoffNotes (not “later-merged”).
5. Merge eligible → integration worktree.
6. If conflict set `|C|≥2` → **demotion SM** (§D.4.4): supersede all of C; orient; amend **active** plan; do **not** leave live `[A,B]+[B]`.
7. Pure amendment for deps affecting only undispatched work.
8. Batch escalations / needs_manager_attention → ≤1 Manager replan per wave per attempt.
9. Assemble WaveHandoffNote (≤2000 tokens, §B.5 wave→wave).
10. Advance wave or Integration Validator.

Integration Validator runs **once** after the final active wave — not per wave.

## Dependencies

Sections 04–05, Phase 03 RI for caller cross-check.

## Atomic Implementation Tasks

1. Fan-in decision list 1–10 exactly.
2. Demotion state machine S1–S7 + unit tests (lex order, cycle→replan, 3-way conflict, sibling merge before demote).
3. `demotion_ignore_keys` + `merge_eligible` (do not add `status=superseded`; rows are append-only).
4. WaveHandoffNote assembly + truncate order §D.10.6.
5. Integration Validator + FL-05.
6. Telemetry events: `overlap_detected`, `semantic_conflict`, `wave_demotion`, `plan_amended`, `wave_handoff_assembled`.
7. Tests: zero-overlap semantic conflict; demotion active-plan rewrite; amendment-only path; cross-wave vs merged → replan not demotion.

## Acceptance Criteria

- [ ] Fan-in never silently merges conflicts.
- [ ] Active plan after demotion is rewritten; history is telemetry/topology_decisions — not a live conflicting wave.
- [ ] WaveHandoffNote ≤ 2000 tokens; no raw diffs inlined.
- [ ] Integration Validator once per implementation attempt.
- [ ] No LLM calls inside Fan-in.

## Risks

- File-level overlap false positives — acceptable; revisit with Phase 15 KPIs.
- Amendment/demotion loops — edge add-only + cap.
