"""Planning Manager wired into the Phase 01 compiled graph (still-stub requirements)."""

from __future__ import annotations

import json

from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select
from tests.contract.fakes import FakeAdapter
from tests.factories import make_task

from agents.intake.node import build_intake_node
from common.config import get_settings
from common.db import make_async_engine, make_session_factory, reset_engine
from common.models import CostTrackingRow
from common.task import WorkType
from common.task_repository import create_task, get_task
from common.telemetry import NoOpTelemetrySink
from model_adapters.base import ModelRequest, ModelResponse, TokenUsage
from model_adapters.router import ModelRouter
from orchestration.dag_constructor import PHASE_ORDER, build_graph
from orchestration.runtime import is_interrupted, start_or_continue


class ClassifyAdapter(FakeAdapter):
    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        return ModelResponse(
            content=json.dumps(
                {
                    "work_type": "feature",
                    "risk_tier": "medium",
                    "rationale": "request adds capability to an existing system",
                    "confidence": 0.91,
                }
            ),
            usage=TokenUsage(input_tokens=20, output_tokens=10),
            model_id=self._mid(),
            finish_reason="stop",
        )


async def test_real_intake_runs_then_pauses_at_stub_design(
    migrated_database_url: str, monkeypatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)
    get_settings.cache_clear()
    reset_engine()

    task = make_task(
        id="task-intake-graph",
        title="Add SSO login for existing users",
        type=WorkType.BUG,
    )
    engine = make_async_engine(migrated_database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        await create_task(session, task)

    adapter = ClassifyAdapter(capability_score=6, model_id="fake-small")
    intake = build_intake_node(
        router=ModelRouter([adapter]),
        persist_classification=True,
        sink=NoOpTelemetrySink(),
        architecture_summary_loader=_summary,
        session_factory=factory,
    )
    graph = build_graph(
        checkpointer=InMemorySaver(),
        persist_task_state=True,
        sink=NoOpTelemetrySink(),
        node_overrides={"intake": intake},
    )
    paused = await start_or_continue(graph, task)
    assert is_interrupted(paused)
    assert "design" in tuple(paused.next or ())
    events = paused.values["agent_events"]
    completed_agents = [
        event["agent_id"] for event in events if event["event_type"] == "agent_completed"
    ]
    assert "planning_manager" in completed_agents
    phases = [
        event["phase"] for event in events if event["event_type"] == "phase_completed"
    ]
    assert phases[:2] == ["intake", "requirements"]
    assert set(PHASE_ORDER).issuperset(phases)

    async with factory() as session:
        loaded = await get_task(session, task.id)
        assert loaded is not None
        assert loaded.type == WorkType.FEATURE
        assert loaded.risk_tier.value == "medium"
        costs = await session.execute(
            select(CostTrackingRow).where(CostTrackingRow.task_id == task.id)
        )
        assert costs.scalars().first() is not None

    await engine.dispose()
    reset_engine()
    get_settings.cache_clear()


async def _summary() -> str:
    return json.dumps({"services": ["auth"], "generated_by": "ast"})
