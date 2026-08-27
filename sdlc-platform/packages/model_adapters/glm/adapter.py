"""GLM-4.7 / GLM-4.7-Flash adapter. The only file that talks to the GLM HTTP API.

Uses LangChain ChatOpenAI against Z.AI's OpenAI-compatible chat base URL
(see docs/decisions/2026-08-27-glm-openai-compatibility.md). LiteLLM is not used.

Embeddings still go through OpenAIEmbeddings on the same base URL, but that path
is unverified against current Z.AI docs (no embeddings API in the public index).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from common.config import get_settings
from model_adapters.base import (
    EmbeddingResult,
    ModelChunk,
    ModelPricing,
    ModelRequest,
    ModelResponse,
    TokenUsage,
    ToolSpec,
    Vector,
)
from model_adapters.glm.convert import response_from_message, to_lc_messages, to_openai_tools
from model_adapters.registry import PricingRegistry, load_pricing_registry


class GLMConfigError(RuntimeError):
    """Missing GLM_API_KEY or unknown model_id in the pricing registry."""


class GLMAdapter:
    def __init__(
        self,
        *,
        model_id: str | None = None,
        embed_model_id: str | None = None,
        chat_model: Any | None = None,
        embeddings: Any | None = None,
        registry: PricingRegistry | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        settings = get_settings()
        self._registry = registry or load_pricing_registry()
        self.model_id = model_id or settings.glm_chat_model
        self.embed_model_id = embed_model_id or settings.glm_embed_model
        self._pricing = self._registry.get(self.model_id)
        self._score = self._registry.capability_score(self.model_id)
        self._chat = chat_model
        self._embeddings = embeddings
        self._api_key = api_key if api_key is not None else settings.glm_api_key
        self._base_url = base_url if base_url is not None else settings.glm_base_url

    def complete(self, request: ModelRequest) -> ModelResponse:
        if request.tools:
            return self.call_tools(request, request.tools)
        message = self._llm(request).invoke(to_lc_messages(request.messages))
        return response_from_message(message, self.model_id)

    def stream(self, request: ModelRequest) -> Iterator[ModelChunk]:
        from model_adapters.glm.convert import usage_from_message

        last_usage = None
        for piece in self._llm(request).stream(to_lc_messages(request.messages)):
            content = piece.content if isinstance(getattr(piece, "content", None), str) else ""
            usage = usage_from_message(piece)
            if usage.input_tokens or usage.output_tokens:
                last_usage = usage
            yield ModelChunk(content=content or "", done=False)
        yield ModelChunk(content="", usage=last_usage, done=True)

    def call_tools(self, request: ModelRequest, tools: Sequence[ToolSpec]) -> ModelResponse:
        bound = self._llm(request).bind_tools(to_openai_tools(list(tools)))
        message = bound.invoke(to_lc_messages(request.messages))
        return response_from_message(message, self.model_id)

    def embed(self, texts: list[str]) -> list[Vector]:
        return self.embed_with_usage(texts).vectors

    def embed_with_usage(self, texts: list[str]) -> EmbeddingResult:
        """Return vectors. Usage is only filled when the embedder reports it.

        OpenAIEmbeddings does not expose token usage. Z.AI's current public API
        index (2026-08-27) does not document an embeddings route. We therefore
        mark usage `unavailable` rather than guessing from word counts.
        """
        vectors = [list(map(float, row)) for row in self._embedder().embed_documents(texts)]
        extra = getattr(self._embeddings, "last_usage", None) if self._embeddings is not None else None
        if extra is None:
            usage = TokenUsage(source="unavailable")
        else:
            from model_adapters.glm.convert import usage_from_mapping

            usage = usage_from_mapping(dict(extra))
        return EmbeddingResult(vectors=vectors, usage=usage, model_id=self.embed_model_id)

    @property
    def pricing(self) -> ModelPricing:
        return self._pricing

    @property
    def capability_score(self) -> int:
        return self._score

    def _llm(self, request: ModelRequest):
        if self._chat is not None:
            llm = self._chat
            if request.temperature is not None and hasattr(llm, "temperature"):
                llm.temperature = request.temperature
            return llm
        return self._make_chat(request)

    def _make_chat(self, request: ModelRequest):
        # Imported here so router/telemetry never pull in the OpenAI SDK.
        from langchain_openai import ChatOpenAI

        if not self._api_key:
            raise GLMConfigError("GLM_API_KEY is not set")
        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "api_key": self._api_key,
            "base_url": self._base_url,
            "stream_usage": True,
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        return ChatOpenAI(**kwargs)

    def _embedder(self):
        if self._embeddings is not None:
            return self._embeddings
        from langchain_openai import OpenAIEmbeddings

        if not self._api_key:
            raise GLMConfigError("GLM_API_KEY is not set")
        return OpenAIEmbeddings(
            model=self.embed_model_id,
            api_key=self._api_key,
            base_url=self._base_url,
            check_embedding_ctx_length=False,
        )
