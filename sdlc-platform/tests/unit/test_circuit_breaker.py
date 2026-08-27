"""Circuit breaker open / half-open / closed + pause-don't-fail exception."""

import pytest
from tests.contract.fakes import FakeAdapter

from model_adapters.base import ChatMessage, ModelRequest
from model_adapters.circuit_breaker import CircuitBreaker, CircuitState, ProviderUnavailable

PING = ModelRequest(messages=[ChatMessage(role="user", content="hi")])


def test_opens_after_threshold_and_raises_provider_unavailable() -> None:
    clock = {"now": 0.0}
    breaker = CircuitBreaker(
        failure_threshold=2,
        recovery_timeout_s=10,
        clock=lambda: clock["now"],
    )
    adapter = breaker.protect(FakeAdapter(fail_times=3))
    with pytest.raises(RuntimeError):
        adapter.complete(PING)
    with pytest.raises(RuntimeError):
        adapter.complete(PING)
    assert breaker.state is CircuitState.OPEN
    with pytest.raises(ProviderUnavailable):
        adapter.complete(PING)


def test_half_open_success_closes() -> None:
    clock = {"now": 0.0}
    breaker = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout_s=5,
        clock=lambda: clock["now"],
    )
    flaky = FakeAdapter(fail_times=1)
    adapter = breaker.protect(flaky)
    with pytest.raises(RuntimeError):
        adapter.complete(PING)
    assert breaker.state is CircuitState.OPEN
    clock["now"] = 6.0
    response = adapter.complete(PING)
    assert response.content == "pong"
    assert breaker.state is CircuitState.CLOSED


def test_half_open_failure_reopens() -> None:
    clock = {"now": 0.0}
    breaker = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout_s=5,
        clock=lambda: clock["now"],
    )
    adapter = breaker.protect(FakeAdapter(fail_times=2))
    with pytest.raises(RuntimeError):
        adapter.complete(PING)
    clock["now"] = 6.0
    with pytest.raises(RuntimeError):
        adapter.complete(PING)
    assert breaker.state is CircuitState.OPEN


def test_open_breaker_is_pause_contract() -> None:
    """Phase 05 graph nodes catch ProviderUnavailable and interrupt(); they must not fail the task."""
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_s=60)
    adapter = breaker.protect(FakeAdapter(fail_times=1))
    with pytest.raises(RuntimeError):
        adapter.complete(PING)
    with pytest.raises(ProviderUnavailable) as err:
        adapter.complete(PING)
    assert "pause" in (err.value.__class__.__doc__ or "").lower() or err.value.provider == "glm"
