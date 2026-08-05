# Section 03 — 5-Step Compression Pipeline

## Objective

Implement the full 5-step compression pipeline (§H.3) — structural filtering, deduplication, AST-boundary skeletal compression, LRU eviction, LLM summarization (cheapest first) — engaged whenever Section 01's budget check finds assembled context over budget, with a final fallback to task splitting if still over budget after all five steps.

## Why It Exists

Section 01 establishes the ceiling; this section is what actually brings over-budget context back under it, in a cost-aware order (free structural/deduplication steps first, expensive LLM summarization only as a last resort) — directly implementing Principle 1's "reasoning budget front-loads into requirements and design" philosophy applied at the mechanical context-assembly level.

## Expected Architecture

`packages/context_engine/compressor.py`'s `compress(context_candidates, budget) -> CompressedContext` implements the five steps in order per §H.3, short-circuiting as soon as the result fits budget (no need to run Step 5 if Step 2 already got under budget). Step 3 (AST-boundary skeletal compression) directly builds on Phase 03 §01's Tree-sitter symbol boundaries (replace function bodies with signatures+docstrings; full body available via the existing progressive-expansion tool call, Phase 06 §05, if the agent explicitly requests it). Step 5 (LLM summarization) uses a Fast-tier model call (§I.2's `("any", "summarization")` capability requirement, already defined since Phase 02 §04) to compress cold conversation history. The fallback (still over budget after Step 5 → split into smaller sub-tasks) hooks into Phase 06 §04's Implementation Manager decomposition logic — a task too large to fit even compressed context is itself a decomposition-granularity signal worth surfacing there.

## Dependencies

Section 01 (budget to compress against), Phase 03 §01 (AST boundaries for Step 3), Phase 02 (Fast-tier model for Step 5).

## Atomic Implementation Tasks

1. Implement Step 1 (structural filtering): remove files/symbols not in the dependency graph of changed/relevant modules (uses Phase 03/11's `RepositoryIntelligence`).
2. Implement Step 2 (deduplication): hash-based dedup of repeated code blocks, merge overlapping ranges.
3. Implement Step 3 (AST-boundary skeletal compression): replace bodies with signatures+docstrings by default, expandable via existing tool calls.
4. Implement Step 4 (LRU eviction): evict oldest resolved context chunks, explicitly preserving active constraints/open ambiguities/recent tool results (per §H.3's stated preservation list).
5. Implement Step 5 (LLM summarization): Fast-tier summarization of cold conversation history into a procedural-memory-style block, only invoked if Steps 1–4 leave the context still over budget.
6. Implement the fallback (still over budget → signal task-splitting need to Implementation Manager, Phase 06 §04).
7. Unit tests: each step is independently testable (given known-over-budget input, does Step N produce the expected size reduction and correctly preserve required elements); an end-to-end test confirms the pipeline short-circuits correctly (doesn't run Step 5 when Step 2 already achieves budget) and correctly triggers the fallback when genuinely necessary.

## Manual Testing Procedure

1. Construct a deliberately over-budget context assembly for a demo agent invocation and run it through the pipeline, observing which steps engage and the resulting size at each stage.
2. Confirm Step 3's compression preserves the ability to expand back to full body via existing progressive-context tool calls (Phase 06 §05) — i.e., compression doesn't destroy information, it defers it.
3. Force a genuinely oversized task (more context than even full compression can fit) and confirm the fallback correctly signals Implementation Manager rather than silently truncating something load-bearing.

## Expected Demo

Terminal output showing a step-by-step compression trace for an over-budget context assembly: starting size, size after each of the five steps, and the final under-budget result — with an annotation of which steps were actually engaged (cheapest-first short-circuiting visible).

## Acceptance Criteria

- [ ] All five steps are correctly implemented in the specified cheapest-first order, with short-circuiting once budget is met.
- [ ] Step 3's compression is reversible via existing progressive-expansion tool calls — verified explicitly, not assumed.
- [ ] The fallback (task splitting signal) correctly triggers only when genuinely necessary (all five steps exhausted) and correctly reaches Implementation Manager.

## Risks

- **Risk:** Aggressive compression (especially Step 4's LRU eviction and Step 5's summarization) risks silently dropping information an agent actually needed, degrading output quality in a way that's hard to detect without a dedicated check. **Mitigation:** Section 05's benchmark explicitly measures task success rate alongside token reduction — a token-efficiency win that comes with a success-rate regression is not an acceptable outcome per this phase's own stated goal ("no drop in task success rate").

## Future Improvements

- Smarter Step 4 eviction policies beyond simple LRU (e.g., relevance-weighted eviction) — worth exploring if Section 05's benchmark reveals LRU is too blunt an instrument.

## Research Opportunities

Measure which compression step contributes the most token savings in practice across a range of real tasks — informs whether all five steps are pulling their weight or whether the pipeline could be simplified (directly relevant to this platform's overall "avoid unjustified complexity" principle, §E.2, applied here to context engineering).
