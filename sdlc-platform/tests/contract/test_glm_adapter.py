"""GLMAdapter against the shared contract (mocked HTTP) plus optional live calls."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk
from tests.contract.model_adapter_contract import assert_adapter_satisfies_contract

from common.config import get_settings
from model_adapters.base import ChatMessage, ModelRequest, ToolSpec
from model_adapters.glm.adapter import GLMAdapter


class _FakeChat:
    temperature = 0.0

    def invoke(self, messages, **kwargs):
        return AIMessage(
            content="pong",
            usage_metadata={"input_tokens": 4, "output_tokens": 1, "total_tokens": 5},
            tool_calls=[{"id": "c1", "name": "echo", "args": {"text": "hi"}}],
        )

    def stream(self, messages, **kwargs):
        yield AIMessageChunk(content="po")
        yield AIMessageChunk(
            content="ng",
            usage_metadata={"input_tokens": 4, "output_tokens": 1, "total_tokens": 5},
        )

    def bind_tools(self, tools):
        return self


class _FakeEmbeddings:
    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]


def _mocked_adapter(model_id: str = "glm-4.7-flash") -> GLMAdapter:
    return GLMAdapter(
        model_id=model_id,
        chat_model=_FakeChat(),
        embeddings=_FakeEmbeddings(),
    )


def test_glm_adapter_passes_shared_contract() -> None:
    assert_adapter_satisfies_contract(_mocked_adapter())


def test_glm_flash_and_full_have_distinct_capability_scores() -> None:
    flash = _mocked_adapter("glm-4.7-flash")
    full = _mocked_adapter("glm-4.7")
    assert flash.capability_score == 6
    assert full.capability_score == 9
    assert flash.pricing.input_price_per_1m < full.pricing.input_price_per_1m


def _skip_if_no_key() -> None:
    if not get_settings().glm_api_key:
        pytest.skip("GLM_API_KEY not set; live GLM path unverified in this environment")


@pytest.mark.live
def test_live_glm_complete_has_usage() -> None:
    _skip_if_no_key()
    adapter = GLMAdapter()
    response = adapter.complete(
        ModelRequest(messages=[ChatMessage(role="user", content="Reply with pong only.")])
    )
    assert response.content
    assert response.usage.is_available
    assert response.usage.input_tokens > 0 or response.usage.output_tokens > 0


@pytest.mark.live
def test_live_glm_stream_yields_chunks() -> None:
    _skip_if_no_key()
    adapter = GLMAdapter()
    chunks = list(
        adapter.stream(
            ModelRequest(messages=[ChatMessage(role="user", content="Say hi in one word.")])
        )
    )
    text = "".join(chunk.content for chunk in chunks)
    assert text.strip() or any(chunk.done for chunk in chunks)


@pytest.mark.live
def test_live_glm_call_tools() -> None:
    _skip_if_no_key()
    adapter = GLMAdapter()
    response = adapter.call_tools(
        ModelRequest(
            messages=[ChatMessage(role="user", content="Use echo to return the word ping.")]
        ),
        [
            ToolSpec(
                name="echo",
                description="Echo text back",
                parameters={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            )
        ],
    )
    assert response.tool_calls or response.content


def test_mocked_embed_usage_is_unavailable() -> None:
    result = _mocked_adapter().embed_with_usage(["alpha"])
    assert result.vectors
    assert result.model_id == "embedding-3"
    assert result.usage.source == "unavailable"
    assert result.usage.input_tokens == 0


@pytest.mark.live
def test_live_glm_embed_does_not_invent_usage() -> None:
    """Embeddings are not in the current Z.AI API index. Skip if the endpoint errors."""
    _skip_if_no_key()
    adapter = GLMAdapter()
    try:
        result = adapter.embed_with_usage(["hello from glm embeddings probe"])
    except Exception as exc:  # noqa: BLE001 — live probe; any HTTP/SDK failure means skip
        pytest.skip(f"Z.AI embeddings endpoint not available: {exc}")
    assert result.vectors
    if result.usage.source == "unavailable":
        assert result.usage.input_tokens == 0
        assert result.usage.output_tokens == 0
    else:
        assert result.usage.is_available
