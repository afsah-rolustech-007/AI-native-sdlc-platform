"""Usage telemetry wrapper: BudgetTracker + llm_call spans, no OpenTelemetry import."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from tests.contract.fakes import FakeAdapter

from common.telemetry import RecordingTelemetrySink
from model_adapters.base import ChatMessage, ModelRequest
from model_adapters.registry import UnknownModelError, compute_cost
from model_adapters.telemetry import InstrumentedAdapter


def _request(**overrides) -> ModelRequest:
    fields = {
        "messages": [ChatMessage(role="user", content="hi")],
        "task_id": "task-llm-1",
        "phase": "implementation",
        "agent_id": "coder",
        "operation": "code_generation",
    }
    fields.update(overrides)
    return ModelRequest(**fields)


async def test_instrumented_complete_records_budget_and_span() -> None:
    sink = RecordingTelemetrySink()
    tracker = AsyncMock()
    tracker.record = AsyncMock(return_value=True)
    adapter = InstrumentedAdapter(FakeAdapter(), sink=sink, tracker=tracker)
    response = await adapter.acomplete(_request())
    assert response.content == "pong"
    tracker.record.assert_awaited_once()
    args = tracker.record.await_args.args
    assert args[0] == "task-llm-1"
    assert args[3] == 10
    assert args[4] == 2
    expected = compute_cost(response.usage, adapter.pricing)
    assert args[5] == expected
    assert tracker.record.await_args.kwargs["model_id"] == "fake-small"
    assert sink.started[0]["kind"] == "llm_call"
    assert sink.ended[0]["attributes"]["cost_usd"] == expected
    assert sink.ended[0]["attributes"]["usage_available"] is True


async def test_embed_does_not_invent_tokens_or_write_budget() -> None:
    sink = RecordingTelemetrySink()
    tracker = AsyncMock()
    tracker.record = AsyncMock(return_value=True)
    adapter = InstrumentedAdapter(FakeAdapter(), sink=sink, tracker=tracker)
    vectors = await adapter.aembed(["hello world"])
    assert vectors
    tracker.record.assert_not_awaited()
    assert sink.ended[0]["attributes"]["usage_source"] == "unavailable"
    assert sink.ended[0]["attributes"]["usage_available"] is False
    assert sink.ended[0]["attributes"]["cost_usd"] == 0.0
    assert sink.ended[0]["attributes"]["input_tokens"] == 0


async def test_unknown_response_model_id_is_fail_closed() -> None:
    adapter = InstrumentedAdapter(
        FakeAdapter(response_model_id="not-registered"),
        sink=RecordingTelemetrySink(),
        tracker=AsyncMock(),
    )
    with pytest.raises(UnknownModelError):
        await adapter.acomplete(_request())


async def test_sync_complete_with_tracker_is_rejected() -> None:
    adapter = InstrumentedAdapter(
        FakeAdapter(), sink=RecordingTelemetrySink(), tracker=AsyncMock()
    )
    with pytest.raises(RuntimeError, match="acomplete"):
        adapter.complete(_request())


async def test_sink_failure_does_not_fail_complete() -> None:
    class BoomSink(RecordingTelemetrySink):
        def start_span(self, **kwargs):
            raise RuntimeError("sink down")

        def end_span(self, span_id, **kwargs):
            raise RuntimeError("sink down")

    adapter = InstrumentedAdapter(FakeAdapter(), sink=BoomSink(), tracker=None)
    response = adapter.complete(_request())
    assert response.content == "pong"


async def test_concurrent_acomplete_serializes_budget_writes() -> None:
    sink = RecordingTelemetrySink()
    tracker = AsyncMock()
    tracker.record = AsyncMock(return_value=True)
    adapter = InstrumentedAdapter(FakeAdapter(), sink=sink, tracker=tracker)
    await asyncio.gather(adapter.acomplete(_request()), adapter.acomplete(_request()))
    assert tracker.record.await_count == 2


def test_model_adapters_do_not_import_opentelemetry() -> None:
    root = Path(__file__).resolve().parents[2] / "packages" / "model_adapters"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if "opentelemetry" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(root)))
    assert offenders == []
