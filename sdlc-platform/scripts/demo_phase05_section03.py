"""Phase 05 §03 demo: Planning Manager classifications (scripted Fast-tier JSON).

  uv run python scripts/demo_phase05_section03.py

Uses a fake adapter so CI/demo do not need GLM_API_KEY. Swap in a live adapter
locally if you want to eyeball real model judgment.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from agents.intake.planning_manager import PlanningManager
from common.task import Methodology, RepoRef, RiskTier, Task, WorkType
from common.telemetry import RecordingTelemetrySink
from model_adapters.base import (
    ModelChunk,
    ModelPricing,
    ModelRequest,
    ModelResponse,
    TokenUsage,
)
from model_adapters.router import ModelRouter
from orchestration.masc import MASCEngine
from orchestration.state import initial_sdlc_state

EXAMPLES: list[tuple[str, dict]] = [
    (
        "Add SSO login so employees can use the company IdP",
        {
            "work_type": "feature",
            "risk_tier": "medium",
            "rationale": "New capability on an existing product, not a production outage.",
            "confidence": 0.9,
        },
    ),
    (
        "Login returns 500 when the session cookie expires",
        {
            "work_type": "bug",
            "risk_tier": "high",
            "rationale": "Broken existing behavior for a security-sensitive path.",
            "confidence": 0.88,
        },
    ),
    (
        "Prod payments are failing, hotfix the charge path tonight",
        {
            "work_type": "hotfix",
            "risk_tier": "critical",
            "rationale": "Active production incident language; ship a narrow fix.",
            "confidence": 0.93,
        },
    ),
    (
        "Please look at auth",
        {
            "work_type": "feature",
            "risk_tier": "medium",
            "rationale": "Vague one-liner; defaulting to feature/medium rather than guessing hotfix.",
            "confidence": 0.81,
        },
    ),
    (
        "Greenfield inventory service, empty repo",
        {
            "work_type": "new_project",
            "risk_tier": "high",
            "rationale": "From-scratch system, not an increment on existing code.",
            "confidence": 0.86,
        },
    ),
]


class ScriptedAdapter:
    def __init__(self, body: str) -> None:
        self._body = body
        self._pricing = ModelPricing(
            input_price_per_1m=0.07,
            output_price_per_1m=0.40,
            provider="fake",
            model_id="glm-4.7-flash",
        )

    def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            content=self._body,
            usage=TokenUsage(input_tokens=16, output_tokens=10),
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


def _task() -> Task:
    return Task(
        id="demo-pm",
        title="Classify me",
        source="user_request",
        type=WorkType.FEATURE,
        methodology=Methodology.AGILE,
        repo_refs=[RepoRef(repo_id="demo/app", architecture="monolith")],
        risk_tier=RiskTier.LOW,
        created_at=datetime.now(UTC),
    )


async def _classify(request: str, payload: dict) -> dict:
    adapter = ScriptedAdapter(json.dumps(payload))
    manager = PlanningManager(
        router=ModelRouter([adapter]),
        masc=MASCEngine(),
        sink=RecordingTelemetrySink(),
        request_text=request,
        architecture_summary='{"services":["auth","billing"],"generated_by":"ast"}',
        max_retries=0,
    )
    state = await manager.run(initial_sdlc_state(_task()))
    return state["agent_events"][-1]["payload"]


async def main() -> None:
    print("request → work_type, risk_tier, rationale")
    print("-" * 72)
    for request, payload in EXAMPLES:
        result = await _classify(request, payload)
        print(f"{request}")
        print(f"  {result['work_type']:12} {result['risk_tier']:8}  {result['rationale']}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
