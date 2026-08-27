# GLM Developer API is OpenAI-compatible (chat)

Date: 2026-08-27
Phase: 02 Section 02 (verification spike) + Phase 02 hardening pass

## Question

Is Z.AI / Zhipu GLM's Developer API OpenAI-compatible enough that `GLMAdapter` can be a thin `ChatOpenAI` wrapper, or do we need LiteLLM?

## Finding — chat (verified against live docs)

**Chat is compatible.** Official docs at https://docs.z.ai/guides/develop/openai/python.md and https://docs.z.ai/api-reference/introduction:

- General endpoint: `https://api.z.ai/api/paas/v4/` (this is the documented OpenAI SDK `base_url`).
- Auth: `Authorization: Bearer <API_KEY>`.
- First-class OpenAI SDK path: `OpenAI(api_key=..., base_url="https://api.z.ai/api/paas/v4/")` then `chat.completions.create`.
- LangChain docs use `ChatOpenAI(..., openai_api_base="https://api.z.ai/api/paas/v4/")`.
- Streaming and function calling are documented as OpenAI-shaped.

A live `GLM_API_KEY` is still required to prove token `usage` fields round-trip through LangChain on this account.

## Finding — embeddings (not equivalent to chat)

Current Z.AI public API index (https://docs.z.ai/llms.txt, captured 2026-08-27) lists Chat Completion, image, video, audio, tokenizer, layout parsing, web search — **no embeddings route**. LangChain integration docs mention `ChatOpenAI` only, not `OpenAIEmbeddings`.

The previous assumption that `embedding-3` exists on the same `/embeddings` path is **unverified**. Chat compatibility does not prove embedding compatibility.

`GLMAdapter` still implements Protocol `embed()` via `OpenAIEmbeddings` on `GLM_BASE_URL` so the interface exists, but:

- usage is marked `TokenUsage.source="unavailable"` unless the embedder exposes `last_usage`
- InstrumentedAdapter **does not** invent word-count tokens or write a billed `cost_tracking` row for unavailable usage

## Decision

Keep `GLMAdapter` chat as `langchain_openai.ChatOpenAI` against `https://api.z.ai/api/paas/v4/`. Do **not** introduce LiteLLM. Do **not** import `zai` / `zhipuai`.

## Follow-ups

- Live-prove chat usage → pricing → `cost_tracking` when `GLM_API_KEY` is present.
- Live-prove or delete the embeddings client once Z.AI documents (or rejects) `/embeddings`.
