"""ModelAdapter Protocol and boundary schemas (`final_plan.md` §I.1).

Pure interface. No provider SDK, no HTTP, no OpenTelemetry.
`extra="allow"` on ModelRequest so Phase 05 can add fields without a breaking change.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

Vector = list[float]


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None


class ToolSpec(BaseModel):
    """JSON-schema tool definition. Not a LangChain tool object."""

    name: str
    description: str = ""
    parameters: dict = Field(default_factory=dict)


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict = Field(default_factory=dict)


class TokenUsage(BaseModel):
    """Token counts used for cost. `source` says whether they are real."""

    input_tokens: int = 0
    output_tokens: int = 0
    # "unavailable" means we must not invent counts (e.g. embeddings via OpenAIEmbeddings).
    source: Literal["provider", "unavailable"] = "provider"

    @property
    def is_available(self) -> bool:
        return self.source == "provider"


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    messages: list[ChatMessage]
    tools: list[ToolSpec] | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stop: list[str] | None = None
    response_format: dict | None = None
    # Call-site context for usage telemetry. Phase 05 agents fill these in.
    task_id: str | None = None
    phase: str | None = None
    agent_id: str | None = None
    operation: str | None = None


class ModelChunk(BaseModel):
    content: str = ""
    tool_call_delta: dict | None = None
    usage: TokenUsage | None = None
    done: bool = False


class ModelResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    model_id: str
    finish_reason: str | None = None


class ModelPricing(BaseModel):
    input_price_per_1m: float
    output_price_per_1m: float
    provider: str
    model_id: str


class EmbeddingResult(BaseModel):
    """Vectors plus optional usage. Protocol.embed still returns only vectors."""

    vectors: list[Vector]
    usage: TokenUsage
    model_id: str


@runtime_checkable
class ModelAdapter(Protocol):
    """All orchestration/agent code talks to this — never to a provider SDK."""

    def complete(self, request: ModelRequest) -> ModelResponse: ...

    def stream(self, request: ModelRequest) -> Iterator[ModelChunk]: ...

    def call_tools(self, request: ModelRequest, tools: Sequence[ToolSpec]) -> ModelResponse: ...

    def embed(self, texts: list[str]) -> list[Vector]: ...

    @property
    def pricing(self) -> ModelPricing: ...

    @property
    def capability_score(self) -> int: ...
