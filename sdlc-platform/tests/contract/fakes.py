"""In-memory ModelAdapter for contract/router tests. No provider SDK."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from model_adapters.base import (
    EmbeddingResult,
    ModelChunk,
    ModelPricing,
    ModelRequest,
    ModelResponse,
    TokenUsage,
    ToolCall,
    ToolSpec,
    Vector,
)


class FakeAdapter:
    def __init__(
        self,
        *,
        model_id: str = "fake-small",
        provider: str = "fake",
        capability_score: int = 6,
        input_price_per_1m: float = 0.1,
        output_price_per_1m: float = 0.2,
        complete_text: str = "pong",
        fail_times: int = 0,
        response_model_id: str | None = None,
    ) -> None:
        self._pricing = ModelPricing(
            input_price_per_1m=input_price_per_1m,
            output_price_per_1m=output_price_per_1m,
            provider=provider,
            model_id=model_id,
        )
        self._score = capability_score
        self._complete_text = complete_text
        self._fail_times = fail_times
        self._response_model_id = response_model_id
        self.calls = 0

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        self._maybe_fail()
        return ModelResponse(
            content=self._complete_text,
            usage=TokenUsage(input_tokens=10, output_tokens=2),
            model_id=self._mid(),
            finish_reason="stop",
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelChunk]:
        self.calls += 1
        self._maybe_fail()
        yield ModelChunk(content=self._complete_text[:2], done=False)
        yield ModelChunk(
            content=self._complete_text[2:],
            usage=TokenUsage(input_tokens=10, output_tokens=2),
            done=True,
        )

    def call_tools(self, request: ModelRequest, tools: Sequence[ToolSpec]) -> ModelResponse:
        self.calls += 1
        self._maybe_fail()
        name = tools[0].name if tools else "echo"
        return ModelResponse(
            content=None,
            tool_calls=[ToolCall(id="call-1", name=name, arguments={"text": "hi"})],
            usage=TokenUsage(input_tokens=12, output_tokens=8),
            model_id=self._pricing.model_id,
            finish_reason="tool_calls",
        )

    def embed(self, texts: list[str]) -> list[Vector]:
        return self.embed_with_usage(texts).vectors

    def embed_with_usage(self, texts: list[str]) -> EmbeddingResult:
        self.calls += 1
        self._maybe_fail()
        return EmbeddingResult(
            vectors=[[float(len(text)), 0.1] for text in texts],
            usage=TokenUsage(source="unavailable"),
            model_id=self._pricing.model_id,
        )

    def _maybe_fail(self) -> None:
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RuntimeError("simulated provider error")

    def _mid(self) -> str:
        return self._response_model_id or self._pricing.model_id

    @property
    def pricing(self) -> ModelPricing:
        return self._pricing

    @property
    def capability_score(self) -> int:
        return self._score
