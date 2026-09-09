"""Usage telemetry around ModelAdapter calls.

Writes `cost_tracking` via BudgetTracker and an `llm_call` span via TelemetrySink.
Never imports OpenTelemetry. Never uses a provider-reported cost field.

BudgetTracker.record is async and session-bound. Sync Protocol methods never call
asyncio.run() against that session. Await acomplete / acall_tools / aembed / astream.
One InstrumentedAdapter serializes budget writes so concurrent calls cannot share
the same AsyncSession unsafely.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any
from uuid import uuid4

from common.budget import BudgetTracker
from common.telemetry import TelemetrySink
from model_adapters.base import (
    EmbeddingResult,
    ModelAdapter,
    ModelChunk,
    ModelPricing,
    ModelRequest,
    ModelResponse,
    TokenUsage,
    ToolSpec,
    Vector,
)
from model_adapters.registry import (
    PricingRegistry,
    UnknownModelError,
    compute_cost,
    load_pricing_registry,
)

_TRACKER_SYNC_MSG = (
    "InstrumentedAdapter with a BudgetTracker cannot use sync methods; "
    "await acomplete/acall_tools/aembed/astream on the same event loop as the session"
)


class InstrumentedAdapter:
    """Decorates any ModelAdapter with cost rows + llm_call spans."""

    def __init__(
        self,
        inner: ModelAdapter,
        *,
        sink: TelemetrySink,
        tracker: BudgetTracker | None = None,
        registry: PricingRegistry | None = None,
        default_task_id: str = "unattributed",
        default_phase: str = "any",
        default_agent_id: str = "model-adapter",
    ) -> None:
        self._inner = inner
        self._sink = sink
        self._tracker = tracker
        self._registry = registry or load_pricing_registry()
        self._default_task_id = default_task_id
        self._default_phase = default_phase
        self._default_agent_id = default_agent_id
        self._record_lock = asyncio.Lock()

    def complete(self, request: ModelRequest) -> ModelResponse:
        self._reject_sync_tracker()
        return self._sync_response("complete", request, lambda: self._inner.complete(request))

    def stream(self, request: ModelRequest) -> Iterator[ModelChunk]:
        self._reject_sync_tracker()
        yield from self._stream_inner(request)

    def call_tools(self, request: ModelRequest, tools: Sequence[ToolSpec]) -> ModelResponse:
        self._reject_sync_tracker()
        return self._sync_response(
            "call_tools", request, lambda: self._inner.call_tools(request, tools)
        )

    def embed(self, texts: list[str]) -> list[Vector]:
        self._reject_sync_tracker()
        return self._embed_result(texts).vectors

    async def acomplete(self, request: ModelRequest) -> ModelResponse:
        return await self._tracked("complete", request, lambda: self._inner.complete(request))

    async def acall_tools(self, request: ModelRequest, tools: Sequence[ToolSpec]) -> ModelResponse:
        return await self._tracked(
            "call_tools", request, lambda: self._inner.call_tools(request, tools)
        )

    async def aembed(self, texts: list[str]) -> list[Vector]:
        request = ModelRequest(
            messages=[],
            task_id=self._default_task_id,
            phase=self._default_phase,
            agent_id=self._default_agent_id,
            operation="embed",
        )
        span_id, started = self._start_span(request, "embed", model_id=self._embed_model_id())
        try:
            result = self._embed_result(texts)
            latency_ms = int((time.perf_counter() - started) * 1000)
            response = ModelResponse(
                content=None,
                usage=result.usage,
                model_id=result.model_id,
                finish_reason="embed",
            )
            await self._finish(span_id, request, "embed", response, latency_ms)
            return result.vectors
        except Exception as exc:
            self._fail(span_id, exc)
            raise

    async def astream(self, request: ModelRequest) -> AsyncIterator[ModelChunk]:
        operation = request.operation or "stream"
        span_id, started = self._start_span(request, operation)
        pieces: list[str] = []
        usage = TokenUsage(source="unavailable")
        try:
            for chunk in self._inner.stream(request):
                pieces.append(chunk.content or "")
                if chunk.usage is not None:
                    usage = chunk.usage
                yield chunk
            latency_ms = int((time.perf_counter() - started) * 1000)
            response = ModelResponse(
                content="".join(pieces),
                usage=usage,
                model_id=self._inner.pricing.model_id,
            )
            await self._finish(span_id, request, operation, response, latency_ms)
        except Exception as exc:
            self._fail(span_id, exc)
            raise

    def _sync_response(self, operation: str, request: ModelRequest, fn) -> ModelResponse:
        op = request.operation or operation
        span_id, started = self._start_span(request, op)
        try:
            response = fn()
            latency_ms = int((time.perf_counter() - started) * 1000)
            self._end_ok(span_id, request, op, response, latency_ms)
            return response
        except Exception as exc:
            self._fail(span_id, exc)
            raise

    def _stream_inner(self, request: ModelRequest) -> Iterator[ModelChunk]:
        operation = request.operation or "stream"
        span_id, started = self._start_span(request, operation)
        pieces: list[str] = []
        usage = TokenUsage(source="unavailable")
        try:
            for chunk in self._inner.stream(request):
                pieces.append(chunk.content or "")
                if chunk.usage is not None:
                    usage = chunk.usage
                yield chunk
            latency_ms = int((time.perf_counter() - started) * 1000)
            response = ModelResponse(
                content="".join(pieces),
                usage=usage,
                model_id=self._inner.pricing.model_id,
            )
            self._end_ok(span_id, request, operation, response, latency_ms)
        except Exception as exc:
            self._fail(span_id, exc)
            raise

    def _embed_result(self, texts: list[str]) -> EmbeddingResult:
        detailed = getattr(self._inner, "embed_with_usage", None)
        if callable(detailed):
            return detailed(texts)
        vectors = self._inner.embed(texts)
        return EmbeddingResult(
            vectors=vectors,
            usage=TokenUsage(source="unavailable"),
            model_id=self._embed_model_id(),
        )

    def _embed_model_id(self) -> str:
        return getattr(self._inner, "embed_model_id", None) or self._inner.pricing.model_id

    async def _tracked(self, operation: str, request: ModelRequest, fn) -> ModelResponse:
        op = request.operation or operation
        span_id, started = self._start_span(request, op)
        try:
            response = fn()
            latency_ms = int((time.perf_counter() - started) * 1000)
            await self._finish(span_id, request, op, response, latency_ms)
            return response
        except Exception as exc:
            self._fail(span_id, exc)
            raise

    def _start_span(
        self, request: ModelRequest, operation: str, *, model_id: str | None = None
    ) -> tuple[str, float]:
        pricing = self._inner.pricing
        try:
            span_id = self._sink.start_span(
                kind="llm_call",
                name=operation,
                task_id=request.task_id or self._default_task_id,
                phase=request.phase or self._default_phase,
                agent_id=request.agent_id or self._default_agent_id,
                parent_span_id=request.parent_span_id,
                attributes={
                    "model_id": model_id or pricing.model_id,
                    "provider": pricing.provider,
                    "operation": operation,
                },
            )
        except Exception:
            span_id = "telemetry-error"
        return span_id, time.perf_counter()

    async def _finish(
        self,
        span_id: str,
        request: ModelRequest,
        operation: str,
        response: ModelResponse,
        latency_ms: int,
    ) -> None:
        self._end_ok(span_id, request, operation, response, latency_ms)
        if self._tracker is None or not response.usage.is_available:
            return
        pricing = self._lookup_pricing(response.model_id)
        cost_usd = compute_cost(response.usage, pricing)
        async with self._record_lock:
            await self._tracker.record(
                request.task_id or self._default_task_id,
                request.phase or self._default_phase,
                request.agent_id or self._default_agent_id,
                response.usage.input_tokens,
                response.usage.output_tokens,
                cost_usd,
                idempotency_key=uuid4().hex,
                model_id=pricing.model_id,
                latency_ms=latency_ms,
            )

    def _end_ok(
        self,
        span_id: str,
        request: ModelRequest,
        operation: str,
        response: ModelResponse,
        latency_ms: int,
    ) -> None:
        pricing = self._lookup_pricing(response.model_id)
        cost_usd = compute_cost(response.usage, pricing)
        self._safe_end(
            span_id,
            status="ok",
            attributes=_span_attrs(pricing, response, cost_usd, latency_ms, operation),
        )

    def _lookup_pricing(self, model_id: str) -> ModelPricing:
        try:
            return self._registry.get(model_id)
        except UnknownModelError:
            inner = self._inner.pricing
            if inner.model_id == model_id:
                return inner
            raise

    def _fail(self, span_id: str, exc: Exception) -> None:
        self._safe_end(
            span_id,
            status="error",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

    def _safe_end(self, span_id: str, **kwargs: Any) -> None:
        try:
            self._sink.end_span(span_id, **kwargs)
        except Exception:
            return

    def _reject_sync_tracker(self) -> None:
        if self._tracker is not None:
            raise RuntimeError(_TRACKER_SYNC_MSG)

    @property
    def pricing(self) -> ModelPricing:
        return self._inner.pricing

    @property
    def capability_score(self) -> int:
        return self._inner.capability_score


def _span_attrs(
    pricing: ModelPricing,
    response: ModelResponse,
    cost_usd: float,
    latency_ms: int,
    operation: str,
) -> dict:
    return {
        "model_id": pricing.model_id,
        "provider": pricing.provider,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "operation": operation,
        "usage_source": response.usage.source,
        "usage_available": response.usage.is_available,
    }
