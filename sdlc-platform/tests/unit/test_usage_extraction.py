"""Usage extraction from LangChain / OpenAI-shaped payloads."""

from types import SimpleNamespace

from model_adapters.base import TokenUsage
from model_adapters.glm.convert import usage_from_mapping, usage_from_message


def test_usage_from_langchain_metadata() -> None:
    message = SimpleNamespace(usage_metadata={"input_tokens": 11, "output_tokens": 3})
    usage = usage_from_message(message)
    assert usage == TokenUsage(input_tokens=11, output_tokens=3, source="provider")
    assert usage.is_available


def test_usage_from_openai_prompt_completion_aliases() -> None:
    usage = usage_from_mapping({"prompt_tokens": 8, "completion_tokens": 2})
    assert usage.input_tokens == 8
    assert usage.output_tokens == 2
    assert usage.source == "provider"


def test_usage_from_response_metadata_token_usage() -> None:
    message = SimpleNamespace(
        usage_metadata=None,
        response_metadata={"token_usage": {"prompt_tokens": 5, "completion_tokens": 1}},
    )
    usage = usage_from_message(message)
    assert usage.input_tokens == 5
    assert usage.output_tokens == 1


def test_missing_usage_is_unavailable_not_zero_provider() -> None:
    usage = usage_from_message(SimpleNamespace(usage_metadata=None, response_metadata={}))
    assert usage.source == "unavailable"
    assert not usage.is_available
    assert usage.input_tokens == 0
