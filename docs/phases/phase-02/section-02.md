# Section 02 — GLM Adapter Implementation

## Objective

Implement `GLMAdapter`, the concrete `ModelAdapter` for GLM-4.7 / GLM-4.7-Flash, after first verifying GLM's Developer API OpenAI-compatibility against live documentation — the blueprint explicitly flags this as unverified (§I.1) and names it as one of three things to check before implementation.

## Why It Exists

This is the platform's first real, live LLM call. Everything about how agents will eventually call models is proven here first, in isolation, without any agent logic complicating the picture.

## Expected Architecture

If GLM's endpoint is OpenAI-compatible (expected, per the blueprint's assumption), `GLMAdapter` is a thin wrapper around `ChatOpenAI` configured with GLM's base URL and API key, implementing the `ModelAdapter` Protocol by delegating to the underlying `BaseChatModel`. If compatibility gaps are found, LiteLLM becomes the normalization layer between `GLMAdapter` and the raw HTTP endpoint — introduced only if actually needed (YAGNI, per `techstack.md`).

## Dependencies

Section 01 (Protocol + contract test suite).

## Atomic Implementation Tasks

1. **Verification spike (do this first, before writing adapter code):** check GLM Developer API's live documentation for OpenAI-compatibility (chat completions shape, tool-calling shape, streaming shape, embeddings endpoint if used). Record the finding in `docs/decisions/` regardless of outcome.
2. Implement `GLMAdapter(complete, stream, call_tools, embed)` per the verification's findings.
3. Implement `GLMAdapter.pricing` and `capability_score` (score `GLM-4.7` and `GLM-4.7-Flash` per the two-tier capability distinction implied throughout §I.2's `CAPABILITY_REQUIREMENTS` table — flash is the "fast/cheap" tier, `GLM-4.7` is "balanced/frontier").
4. Wire API key loading through `packages/common/config.py` (never hard-coded, never read via raw `os.environ` outside that module).
5. Run the Section 01 contract test suite against `GLMAdapter` — this must pass fully before the adapter is considered done.
6. Write a live smoke test (marked `@pytest.mark.live` or similar, excluded from default CI runs to avoid cost/flakiness, run manually or in a scheduled job) that makes one real API call.

## Manual Testing Procedure

1. Run the live smoke test manually: `pytest tests/contract/test_glm_adapter.py -m live -v`.
2. Confirm a real completion is returned with correctly populated usage fields.
3. Test the streaming path manually via a small script, confirming chunks arrive incrementally.
4. Test `call_tools` with one trivial tool definition, confirming the adapter correctly surfaces a tool call request in `ModelResponse`.

## Expected Demo

Terminal output of a live GLM completion, followed by the same request run through `stream()` showing incremental token output, followed by a `call_tools` example showing a structured tool-call response — three call shapes proven live against the real GLM API.

## Acceptance Criteria

- [ ] The GLM-compatibility verification finding is documented (compatible, or documented workaround) before any adapter code depends on an assumption.
- [ ] `GLMAdapter` passes 100% of the shared contract test suite from Section 01.
- [ ] `complete`, `stream`, and `call_tools` are each proven against a live call, not just mocked.
- [ ] No GLM/OpenAI SDK import exists outside `packages/model_adapters/glm/`.

## Risks

- **Risk:** GLM's tool-calling format has subtle differences from OpenAI's that only surface under real usage (e.g., parallel tool calls, streaming tool-call deltas). **Mitigation:** the contract test suite explicitly exercises tool-calling, and any discovered gap gets patched inside `GLMAdapter` (or the LiteLLM layer) — never by an agent working around it later.

## Future Improvements

- LiteLLM introduction, if compatibility gaps are found — tracked as a direct consequence of this section's verification step, not a separate speculative task.

## Research Opportunities

Compare GLM-4.7 vs. GLM-4.7-Flash actual output quality on a few representative prompts from later phases (design reasoning, code generation) once those prompts exist (Phase 05+) — informs the `capability_score` values assigned here, which are otherwise a reasonable starting guess.
