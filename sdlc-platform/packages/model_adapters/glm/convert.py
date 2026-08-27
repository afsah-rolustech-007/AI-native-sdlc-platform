"""LangChain message conversion. Isolated so adapter.py stays the HTTP/SDK owner."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from model_adapters.base import ChatMessage, ModelResponse, TokenUsage, ToolCall, ToolSpec


def to_lc_messages(messages: list[ChatMessage]) -> list[BaseMessage]:
    converted: list[BaseMessage] = []
    for message in messages:
        if message.role == "system":
            converted.append(SystemMessage(content=message.content or ""))
        elif message.role == "user":
            converted.append(HumanMessage(content=message.content or ""))
        elif message.role == "tool":
            converted.append(
                ToolMessage(
                    content=message.content or "",
                    tool_call_id=message.tool_call_id or "",
                    name=message.name,
                )
            )
        else:
            converted.append(AIMessage(content=message.content or ""))
    return converted


def to_openai_tools(tools: list[ToolSpec]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters or {"type": "object", "properties": {}},
            },
        }
        for spec in tools
    ]


def usage_from_message(message: Any) -> TokenUsage:
    meta = getattr(message, "usage_metadata", None)
    if meta is None:
        response_meta = getattr(message, "response_metadata", None) or {}
        if isinstance(response_meta, dict):
            token_usage = response_meta.get("token_usage") or response_meta.get("usage") or {}
            if token_usage:
                return usage_from_mapping(token_usage)
        return TokenUsage(source="unavailable")
    if isinstance(meta, dict):
        return usage_from_mapping(meta)
    return TokenUsage(
        input_tokens=int(getattr(meta, "input_tokens", 0) or 0),
        output_tokens=int(getattr(meta, "output_tokens", 0) or 0),
        source="provider",
    )


def usage_from_mapping(meta: dict) -> TokenUsage:
    input_tokens = int(meta.get("input_tokens") or meta.get("prompt_tokens") or 0)
    output_tokens = int(meta.get("output_tokens") or meta.get("completion_tokens") or 0)
    return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, source="provider")


def tool_calls_from_message(message: Any) -> list[ToolCall]:
    raw = getattr(message, "tool_calls", None) or []
    calls: list[ToolCall] = []
    for item in raw:
        if isinstance(item, dict):
            args = item.get("args") or item.get("arguments") or {}
            if isinstance(args, str):
                args = {"_raw": args}
            calls.append(
                ToolCall(
                    id=str(item.get("id") or item.get("index") or ""),
                    name=str(item.get("name") or ""),
                    arguments=dict(args) if isinstance(args, dict) else {},
                )
            )
            continue
        args = getattr(item, "args", None) or {}
        calls.append(
            ToolCall(
                id=str(getattr(item, "id", "")),
                name=str(getattr(item, "name", "")),
                arguments=dict(args) if isinstance(args, dict) else {},
            )
        )
    return calls


def response_from_message(message: Any, model_id: str) -> ModelResponse:
    content = message.content if isinstance(getattr(message, "content", None), str) else ""
    return ModelResponse(
        content=content or None,
        tool_calls=tool_calls_from_message(message),
        usage=usage_from_message(message),
        model_id=model_id,
        finish_reason=getattr(message, "response_metadata", {}).get("finish_reason")
        if isinstance(getattr(message, "response_metadata", None), dict)
        else None,
    )
