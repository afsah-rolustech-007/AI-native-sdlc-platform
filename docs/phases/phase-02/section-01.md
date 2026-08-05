# Section 01 — ModelAdapter Protocol & Request/Response Schemas

## Objective

Define the `ModelAdapter` Protocol and its supporting Pydantic schemas (`ModelRequest`, `ModelResponse`, `ModelChunk`, `ModelPricing`, `ToolSpec`) exactly as specified in §I.1, using `langchain_core.language_models.BaseChatModel` as the underlying base per the blueprint's explicit build choice.

## Why It Exists

This interface is the seam that makes Principle 6 ("Model- and tool-independence is structural") real. Every later phase's agents, the Feedback Agent's escalation logic (Phase 06), and Phase 16's "add a second provider with zero orchestration changes" acceptance test all depend on this boundary being drawn correctly and completely from the start.

## Expected Architecture

`packages/model_adapters/base.py` defines the `ModelAdapter` `Protocol` with `complete`, `stream`, `call_tools`, `embed` methods and `pricing`/`capability_score` properties, per §I.1. Request/response schemas are Pydantic models so they validate at the boundary the same way `Task` does. No concrete provider logic lives in this file — it is pure interface.

## Dependencies

None beyond Phase 00 (no functional dependency, but this section is sequenced first within Phase 02 since Section 02 implements against it).

## Atomic Implementation Tasks

1. Add `langchain-core` and `langgraph` to `pyproject.toml` (the second wave of LangGraph-family dependencies, after Phase 01's checkpointer package).
2. Implement `ModelRequest` (messages, tools, temperature, max_tokens, etc.) and `ModelResponse` (content, tool_calls, usage) schemas.
3. Implement `ModelPricing` (`input_price_per_1m`, `output_price_per_1m`, `provider`, `model_id`).
4. Implement the `ModelAdapter` Protocol per §I.1's exact method signatures.
5. Write a `tests/contract/model_adapter_contract.py` — a shared, reusable contract test suite that *any* future adapter implementation must pass (this file itself doesn't test a concrete adapter yet; it's the shared harness Section 02 will run against `GLMAdapter`, and Phase 16 will run against the second provider).

## Manual Testing Procedure

1. Verify the Protocol type-checks correctly against a trivial mock implementation (mypy should flag a mock missing a method).
2. Review the contract test file to confirm it exercises every method in the Protocol without referencing any concrete provider.

## Expected Demo

A `mypy` run showing a deliberately incomplete mock adapter fails type-checking with a clear "missing method" error — proving the Protocol is enforced, not just documented.

## Acceptance Criteria

- [ ] `ModelAdapter` Protocol matches §I.1's method signatures exactly.
- [ ] Request/response schemas are Pydantic-validated, matching the fields real agents will need (messages, tools, streaming chunks, usage).
- [ ] A shared contract test suite exists and is provider-agnostic (imports no concrete adapter).

## Risks

- **Risk:** Under-specifying `ModelRequest` now and needing breaking changes once real agent prompts (Phase 05) reveal missing fields (e.g., response format constraints for structured output). **Mitigation:** treat this schema as versioned/extensible from the start (e.g., avoid `Extra.forbid` config unless deliberately locking down); expect at least one revision once Phase 05's structured-output needs are concrete, and treat that revision as normal, not as a design failure.

## Future Improvements

- LiteLLM normalization layer — only if Section 02 discovers GLM compatibility gaps (§I.1).

## Research Opportunities

None.
