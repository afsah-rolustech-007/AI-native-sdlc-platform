# Phase 02 — Model Abstraction Layer

## Goal

Make model-independence a structural property of the codebase, not a convention to remember. By the end of this phase, every future agent will call a `ModelAdapter`, never a provider SDK, and cost/usage is tracked uniformly regardless of which model answered.

## Why This Phase Exists

Phase 05 is the first phase to make a real LLM call. If the adapter boundary isn't in place before that call is written, the first agent sets a bad precedent (direct SDK import) that every subsequent agent copies. Building this in parallel with Phase 01 (both depend only on Phase 00) means it's ready the moment agents need it. Corresponds to `final_plan.md` §I.

## Dependencies

Phase 00 (config/secrets loading for API keys, cost tracking table, OTel tracing to attach usage telemetry to).

## High-Level Architecture

```
Agent code (Phase 05+)
        │  calls only this interface
        ▼
  ModelAdapter (Protocol)
   ├── complete(request) -> ModelResponse
   ├── stream(request) -> Iterator[ModelChunk]
   ├── call_tools(request, tools) -> ModelResponse
   ├── embed(texts) -> list[Vector]
   ├── pricing -> ModelPricing
   └── capability_score -> int (1-10)
        │
        ▼
  GLMAdapter (implements ModelAdapter, wraps LangChain BaseChatModel)
        │
        ▼
  UsageTelemetry callback ──▶ BudgetTracker.record() (Phase 00 §03) + OTel span (Phase 00 §05)
```

No agent, orchestration node, or API handler ever imports a provider SDK (`zhipuai`, `openai`, etc.) directly — this is enforced by a CI grep check, not just code review discipline.

## Expected Live Demo

A CLI script that calls `ModelAdapter.complete()` against the live GLM adapter with a trivial prompt, prints the response, and then queries `cost_tracking` to show the exact cost/token row that call produced — proving the full path from LLM call to auditable cost record works, before any agent exists to hide behind.

## Deliverables

- `packages/model_adapters/base.py` — `ModelAdapter` Protocol, `ModelRequest`/`ModelResponse`/`ModelPricing` schemas.
- `packages/model_adapters/glm/adapter.py` — GLM adapter (verified OpenAI-compatible or wrapped appropriately).
- `packages/model_adapters/telemetry.py` — usage callback wired to Phase 00's `BudgetTracker` and OTel.
- `packages/model_adapters/registry.py` — versioned pricing registry.
- Basic `ModelRouter.select()` (capability-requirement lookup only — full escalation logic is Phase 10).
- CI check: zero provider SDK imports outside `model_adapters/`.

## Sections

1. [ModelAdapter Protocol & Request/Response Schemas](section-01.md)
2. [GLM Adapter Implementation](section-02.md)
3. [Cost Tracking, Pricing Registry & Usage Telemetry](section-03.md)
4. [Basic Model Router & Circuit Breaker](section-04.md)
