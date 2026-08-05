# Section 04 — Real Phase Handoff Packets

## Objective

Implement the real `PhaseHandoffPacket` (§B.5) — decisions with rationale pointers, open assumptions, confidence at handoff, artifact refs (pointer-based, not inlined), and a hard per-transition token cap — replacing the raw artifact-passing pattern used between phases since Phase 05 (where `SDLCState.requirements`/`architecture`/etc. were read directly by the next phase's agents, with no formal size discipline).

## Why It Exists

§B.5 is explicit: this is "the mechanism that bounds context growth across phase transitions... without this, context grows unboundedly across feedback-loop revisits." Every feedback loop built since Phase 06 (`FL-02` through `FL-11`) re-enters a phase, and without a bounded handoff mechanism, repeated re-entries could accumulate ever-larger context. This section closes that gap.

## Expected Architecture

`packages/context_engine/handoff_packet.py` implements `PhaseHandoffPacket` exactly per §B.5's YAML schema, with the exact per-transition token caps from §B.5's table (Requirements→Design: 2,000; Design→Implementation manager: 3,000; Design→Implementation per sub-task: 1,500; Implementation→QA: 2,000; QA→Deployment: 1,000; Any→HITL: 3,000). Every phase-transition point built since Phase 05 (Requirements exit into Design, Design approval into Implementation, Implementation completion into QA, QA pass into Release, every `ApprovalGate`'s evidence bundle) is retrofitted to construct and pass a `PhaseHandoffPacket` instead of raw `SDLCState` field access — using Section 03's compression pipeline internally to fit the packet's size budget, with lowest-relevance items dropping to pointer-only per §B.5's stated behavior.

## Dependencies

Section 03 (compression pipeline to fit packets within budget), every phase-transition point built in Phases 05–08.

## Atomic Implementation Tasks

1. Implement `PhaseHandoffPacket` per §B.5's exact schema.
2. Implement packet construction at each transition point, with the exact token caps from §B.5's table enforced (using Section 03's pipeline to compress content that would otherwise exceed the cap, converting overflow items to pointer-only references).
3. Retrofit Requirements→Design (Phase 05 §04/§05 → Phase 06 §01), Design→Implementation (Phase 06 §03 → §04, both the manager-level and per-sub-task-level packets), Implementation→QA (Phase 06 §07 → Phase 07 §01), QA→Deployment (Phase 07 §05 → Phase 08 §05), and every `ApprovalGate`'s evidence-bundle construction (Phase 08 §02) to use real `PhaseHandoffPacket`s instead of raw state access.
4. Update the incoming phase's context-assembly logic (`BaseAgent.build_context()`) to treat the handoff packet as *primary* context, with full upstream detail retrieved on-demand via tool call only if genuinely needed — per §B.5's explicit behavior ("Full upstream detail is retrieved via tool call only if the incoming agent's own retrieval step determines it's actually needed").
5. Integration tests: re-run every existing feedback-loop scenario (Phase 06's `FL-02`/`FL-03`, `FL-04`/`FL-05`; Phase 07's `FL-06`/`FL-07`) and confirm re-entry into a phase now uses a properly bounded handoff packet rather than accumulating unbounded context across repeated loop iterations — this is the section's core correctness proof, directly testing the "without this, context grows unboundedly across feedback-loop revisits" claim from §B.5.

## Manual Testing Procedure

1. Run the demo feature through a full pipeline and inspect each transition's `PhaseHandoffPacket`, confirming it respects its token cap.
2. Force a feedback loop to fire multiple times (e.g., `FL-02` hitting its 5× cap) and confirm the handoff packet size does not grow unboundedly across iterations — measure and plot/print packet size per iteration to prove this directly.
3. Confirm an agent receiving a handoff packet correctly falls back to a tool-call retrieval for detail not included in the packet, rather than failing or hallucinating.

## Expected Demo

A printed sequence of `PhaseHandoffPacket` sizes across a forced multi-iteration feedback loop, showing the size staying bounded (flat or near-flat) rather than growing with each iteration — the direct, visual proof of this section's reason for existing.

## Acceptance Criteria

- [ ] Every phase transition uses a real `PhaseHandoffPacket` respecting §B.5's exact per-transition token caps.
- [ ] Repeated feedback-loop re-entry into a phase does not cause unbounded context growth — verified by the multi-iteration size-tracking test.
- [ ] Agents correctly retrieve additional detail on-demand via tool calls when the handoff packet alone is insufficient, rather than failing.

## Risks

- **Risk:** Overly aggressive pointer-only demotion at a tight token cap could omit something an agent needed, forcing excessive tool-call retrieval that partially defeats the efficiency goal. **Mitigation:** Section 05's benchmark measures both token reduction and tool-call volume — a reduction in handoff packet size that's offset by a large increase in retrieval tool calls is a wash, not a win, and worth investigating if observed.

## Future Improvements

- Per-transition cap tuning based on real observed sufficiency (Phase 15's context-efficiency KPI, §L.2) — the caps from §B.5 are reasonable starting values, not necessarily final.

## Research Opportunities

Measure correlation between handoff packet "relevance drop to pointer-only" decisions and subsequent tool-call retrieval of exactly those dropped items — if a particular field is almost always retrieved anyway, it probably shouldn't have been dropped to pointer-only in the first place, suggesting the relevance-ranking heuristic needs tuning.
