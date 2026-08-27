"""Circuit breaker for provider unavailability (`final_plan.md` §I.3).

When open, callers must pause the task (LangGraph interrupt / checkpoint), not fail it.
Phase 05 wires that into a real agent node. This module only defines the contract.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Sequence
from enum import Enum

from common.config import get_settings
from model_adapters.base import (
    ModelAdapter,
    ModelChunk,
    ModelPricing,
    ModelRequest,
    ModelResponse,
    ToolSpec,
    Vector,
)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ProviderUnavailable(Exception):
    """Breaker is open. Graph code must catch this and pause — never mark the task failed."""

    def __init__(self, provider: str, message: str = "provider circuit open") -> None:
        self.provider = provider
        super().__init__(f"{provider}: {message}")


class CircuitBreaker:
    def __init__(
        self,
        *,
        provider: str = "glm",
        failure_threshold: int | None = None,
        recovery_timeout_s: float | None = None,
        success_threshold: int = 1,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        settings = get_settings()
        self.provider = provider
        self.failure_threshold = (
            failure_threshold
            if failure_threshold is not None
            else settings.circuit_breaker_failure_threshold
        )
        self.recovery_timeout_s = (
            recovery_timeout_s
            if recovery_timeout_s is not None
            else settings.circuit_breaker_recovery_timeout_s
        )
        self.success_threshold = success_threshold
        self._clock = clock
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.half_open_successes = 0
        self.opened_at: float | None = None

    def allow(self) -> None:
        """Raise ProviderUnavailable when the caller must pause instead of calling the model."""
        if self.state is CircuitState.CLOSED:
            return
        if self.state is CircuitState.HALF_OPEN:
            return
        elapsed = self._clock() - (self.opened_at or 0.0)
        if elapsed >= self.recovery_timeout_s:
            self.state = CircuitState.HALF_OPEN
            self.half_open_successes = 0
            return
        raise ProviderUnavailable(self.provider)

    def record_success(self) -> None:
        if self.state is CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= self.success_threshold:
                self._close()
            return
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.state is CircuitState.HALF_OPEN:
            self._open()
            return
        if self.consecutive_failures >= self.failure_threshold:
            self._open()

    def _open(self) -> None:
        self.state = CircuitState.OPEN
        self.opened_at = self._clock()
        self.half_open_successes = 0

    def _close(self) -> None:
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.opened_at = None
        self.half_open_successes = 0

    def protect(self, adapter: ModelAdapter) -> ModelAdapter:
        return ProtectedAdapter(adapter, self)


class ProtectedAdapter:
    """ModelAdapter that pauses-via-exception when the breaker is open."""

    def __init__(self, inner: ModelAdapter, breaker: CircuitBreaker) -> None:
        self._inner = inner
        self._breaker = breaker

    def complete(self, request: ModelRequest) -> ModelResponse:
        return self._call(self._inner.complete, request)

    def stream(self, request: ModelRequest) -> Iterator[ModelChunk]:
        self._breaker.allow()
        try:
            yield from self._inner.stream(request)
        except ProviderUnavailable:
            raise
        except Exception:
            self._breaker.record_failure()
            raise
        self._breaker.record_success()

    def call_tools(self, request: ModelRequest, tools: Sequence[ToolSpec]) -> ModelResponse:
        return self._call(lambda req: self._inner.call_tools(req, tools), request)

    def embed(self, texts: list[str]) -> list[Vector]:
        self._breaker.allow()
        try:
            result = self._inner.embed(texts)
        except ProviderUnavailable:
            raise
        except Exception:
            self._breaker.record_failure()
            raise
        self._breaker.record_success()
        return result

    def _call(self, fn, request: ModelRequest) -> ModelResponse:
        self._breaker.allow()
        try:
            result = fn(request)
        except ProviderUnavailable:
            raise
        except Exception:
            self._breaker.record_failure()
            raise
        self._breaker.record_success()
        return result

    @property
    def pricing(self) -> ModelPricing:
        return self._inner.pricing

    @property
    def capability_score(self) -> int:
        return self._inner.capability_score
