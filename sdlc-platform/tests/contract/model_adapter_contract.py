"""Shared, provider-agnostic ModelAdapter contract.

This module must not import a concrete adapter or any provider SDK.
Future adapters call `assert_adapter_satisfies_contract`.
"""

from __future__ import annotations

from collections.abc import Iterator

from model_adapters.base import (
    ChatMessage,
    ModelAdapter,
    ModelChunk,
    ModelRequest,
    ModelResponse,
    ToolSpec,
)

PING = ModelRequest(messages=[ChatMessage(role="user", content="Reply with the single word pong.")])
ECHO_TOOL = ToolSpec(
    name="echo",
    description="Return the provided text unchanged.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
)


def assert_adapter_satisfies_contract(adapter: ModelAdapter) -> None:
    """Exercise every Protocol method. Safe against a mocked or live adapter."""
    assert 1 <= adapter.capability_score <= 10
    assert adapter.pricing.model_id
    assert adapter.pricing.provider
    assert adapter.pricing.input_price_per_1m >= 0
    assert adapter.pricing.output_price_per_1m >= 0

    complete = adapter.complete(PING)
    assert isinstance(complete, ModelResponse)
    assert complete.model_id == adapter.pricing.model_id
    assert complete.usage.input_tokens >= 0
    assert complete.usage.output_tokens >= 0

    chunks = list(adapter.stream(PING))
    assert chunks
    assert isinstance(chunks[0], ModelChunk)
    assert any(chunk.content or chunk.done for chunk in chunks)
    assert isinstance(adapter.stream(PING), Iterator)

    tooled = adapter.call_tools(
        ModelRequest(
            messages=[ChatMessage(role="user", content="Call echo with text=hi")],
        ),
        [ECHO_TOOL],
    )
    assert isinstance(tooled, ModelResponse)
    assert tooled.content is not None or tooled.tool_calls

    vectors = adapter.embed(["alpha", "beta"])
    assert len(vectors) == 2
    assert all(isinstance(axis, float) for axis in vectors[0])
