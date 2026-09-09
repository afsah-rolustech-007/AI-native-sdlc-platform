"""Phase 05 §01 demo: EchoAgent through MASC three ways.

  uv run python scripts/demo_phase05_section01.py

No network. A fake adapter returns the JSON body we pass in.
"""

from __future__ import annotations

import asyncio
import json

from pydantic import BaseModel

from agents.base import BaseAgent
from common.task import Methodology, RepoRef, RiskTier, Task, WorkType
from common.telemetry import RecordingTelemetrySink
from model_adapters.base import (
    ChatMessage,
    ModelChunk,
    ModelPricing,
    ModelRequest,
    ModelResponse,
    TokenUsage,
)
from model_adapters.router import ModelRouter
from orchestration.masc import MASCEngine, MASCValidationError
from orchestration.state import SDLCState, initial_sdlc_state


class EchoOutput(BaseModel):
    echo: str
    confidence: float


class FixedAdapter:
    """Minimal ModelAdapter: always returns the same JSON string."""

    def __init__(self, body: str) -> None:
        self._body = body
        self._pricing = ModelPricing(
            input_price_per_1m=0.1,
            output_price_per_1m=0.2,
            provider="fake",
            model_id="fake-small",
        )

    def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            content=self._body,
            usage=TokenUsage(input_tokens=8, output_tokens=4),
            model_id=self._pricing.model_id,
            finish_reason="stop",
        )

    def stream(self, request: ModelRequest):
        yield ModelChunk(content=self._body, done=True)

    def call_tools(self, request: ModelRequest, tools):
        return self.complete(request)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    @property
    def pricing(self) -> ModelPricing:
        return self._pricing

    @property
    def capability_score(self) -> int:
        return 6


class EchoAgent(BaseAgent):
    agent_id = "echo"
    phase = "requirements"
    operation = "summarization"

    @property
    def output_schema(self) -> type[BaseModel]:
        return EchoOutput

    def build_context(self, state: SDLCState) -> list[ChatMessage]:
        return [ChatMessage(role="user", content="ping")]


def _task(suffix: str) -> Task:
    return Task(
        id=f"demo-echo-{suffix}",
        title="Echo MASC demo",
        source="user_request",
        type=WorkType.FEATURE,
        methodology=Methodology.AGILE,
        repo_refs=[RepoRef(repo_id="demo/app", architecture="monolith")],
        risk_tier=RiskTier.LOW,
    )


async def _run(label: str, body: dict) -> None:
    sink = RecordingTelemetrySink()
    agent = EchoAgent(
        router=ModelRouter([FixedAdapter(json.dumps(body))]),
        masc=MASCEngine(),
        sink=sink,
        max_retries=0,
    )
    print(f"\n=== {label} ===")
    print(f"model output: {body}")
    try:
        result = await agent.run(initial_sdlc_state(_task(label)))
    except MASCValidationError as exc:
        flag = exc.flag
        print(f"MASC rejected: {flag['flag_type']} ({flag['severity']})")
        print(f"detail: {flag['detail']}")
        print("output did not enter SDLCState")
        return
    payload = result["agent_events"][-1]["payload"]
    kinds = [span["kind"] for span in sink.started]
    print(f"MASC passed; state payload={payload}")
    print(f"spans: {kinds}")


async def main() -> None:
    await _run("valid", {"echo": "hello", "confidence": 0.91})
    await _run("low-confidence", {"echo": "hello", "confidence": 0.40})
    await _run("schema-violation", {"echo": "hello"})


if __name__ == "__main__":
    asyncio.run(main())
