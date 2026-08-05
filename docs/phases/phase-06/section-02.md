# Section 02 — Security Architect & Reflection Pass

## Objective

Implement the Security Architect (conditional agent, §E.8: active when `security_classification != low` OR `touches_shared_infra`) and the reflection/self-critique pass (§M.3) for the Design Manager, both of which improve design quality before it ever reaches `Validator`(design).

## Why It Exists

Security threat modeling and self-critique are exactly the kind of "beyond system prompts" specialization techniques the blueprint calls out explicitly (§E.3, §0.2 #3) as under-addressed by prior designs. Building them now, while Design is still a single-pass agent flow, is cheaper than retrofitting a second-pass review pattern later.

## Expected Architecture

`packages/agents/design/security_architect.py`'s `SecurityArchitect(BaseAgent)` runs at High-capability tier (§E.8), activated conditionally (the activation condition itself is a Fail-Closed-flavored default at this phase — since `security_classification`/`touches_shared_infra` are `WorkflowContext` fields not fully wired until Phase 10, use a conservative heuristic now, e.g., keyword/module-path matching against known-sensitive areas, documented as provisional). It uses a STRIDE threat-model prompt and Semgrep (existing-pattern matching) against relevant code, producing a security addendum appended to `ArchitectureDoc.security_design`. The reflection pass (§M.3) is a second LLM call appended to the Design Manager's flow: "Review your architecture document... identify unaddressed requirements, contradictions, unstated assumptions" — its output is appended to the draft *before* `Validator`(design) sees it (Section 03), per §M.3's stated mechanism for improving first-pass validator acceptance.

## Dependencies

Section 01 (`ArchitectureDoc` to critique/extend).

## Atomic Implementation Tasks

1. Implement the provisional security-sensitivity heuristic (module path / keyword matching against auth, payments, PII-adjacent terms) — document explicitly as a placeholder for Phase 10's real `touches_shared_infra`/`security_classification` `WorkflowContext` fields.
2. Implement `SecurityArchitect` with a STRIDE-based prompt template and Semgrep integration (existing-pattern matching against the affected modules, via the sandbox from Phase 00).
3. Implement the reflection pass as a method on `DesignManager` (or a small wrapping function) per §M.3's exact prompt structure, appending findings to the draft before it's finalized.
4. Wire conditional activation: the `design` node checks the provisional heuristic and only invokes `SecurityArchitect` when triggered — this is the platform's first conditional agent activation, foreshadowing Phase 10's full `F.4` agent-selection rules.
5. Unit/integration tests: a request touching an auth-like module triggers `SecurityArchitect` and produces a non-empty security addendum; a request that doesn't trigger it correctly skips (and this skip is logged, not silent); the reflection pass on a deliberately incomplete draft design surfaces at least one real gap.

## Manual Testing Procedure

1. Run one demo request that should trigger the security heuristic and one that shouldn't; confirm correct activation/skip.
2. Manually review the Security Architect's STRIDE-based findings for plausibility against the demo repo.
3. Manually inspect the reflection pass output on a deliberately weakened design draft (e.g., remove a requirement's coverage) and confirm it's caught.

## Expected Demo

Side-by-side terminal output: a security-triggering request's full addendum, and a non-triggering request's clean skip log — plus a reflection-pass example showing a caught gap on a deliberately weakened draft.

## Acceptance Criteria

- [ ] Security Architect correctly activates/skips per the provisional heuristic, with the decision always logged.
- [ ] Security addendum content is grounded in real Semgrep findings against real code, not fabricated.
- [ ] Reflection pass demonstrably catches at least one class of gap (unaddressed requirement, internal contradiction, unstated assumption) in a controlled test.

## Risks

- **Risk:** The provisional security-sensitivity heuristic is cruder than the real `WorkflowContext.touches_shared_infra` field it stands in for, risking false negatives (missing a genuinely sensitive change). **Mitigation:** bias the heuristic toward over-triggering (false positives are cheap — an unnecessary security review; false negatives are not) until Phase 10 replaces it.

## Future Improvements

- Replace the provisional heuristic with real `WorkflowContext.touches_shared_infra`/`security_classification` — Phase 10.
- Deep CodeQL scanning (currently Semgrep pattern-matching only) — Phase 13.

## Research Opportunities

Measure how often the reflection pass's findings actually change the final design (vs. being ignored/redundant with what `Validator`(design) would have caught anyway) — informs whether the added LLM call is earning its cost, per §M.3's own framing ("adds cost" for high-stakes outputs only).
