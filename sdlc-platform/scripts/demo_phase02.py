"""Phase 02 live demo: ModelAdapter.complete → cost_tracking row.

  make up && make migrate
  GLM_API_KEY=... uv run python scripts/demo_phase02.py

Without GLM_API_KEY the script exits 2 and prints how to configure it.
"""

from __future__ import annotations

import asyncio
import json
import sys

from sqlalchemy import select

from common.budget import BudgetTracker
from common.config import get_settings
from common.db import make_async_engine, make_session_factory
from common.models import CostTrackingRow
from common.task import Methodology, RepoRef, RiskTier, Task, WorkType
from common.task_repository import create_task, get_task
from common.telemetry import RecordingTelemetrySink
from model_adapters.base import ChatMessage, ModelRequest
from model_adapters.glm.adapter import GLMAdapter
from model_adapters.router import ModelRouter
from model_adapters.telemetry import InstrumentedAdapter


async def _run() -> int:
    settings = get_settings()
    if not settings.glm_api_key:
        print("GLM_API_KEY is empty. Set it in .env (see .env.example) and retry.", file=sys.stderr)
        return 2

    engine = make_async_engine(settings.database_url)
    factory = make_session_factory(engine)
    task = Task(
        id="demo-phase02",
        title="Phase 02 model adapter demo",
        source="user_request",
        type=WorkType.FEATURE,
        methodology=Methodology.AGILE,
        repo_refs=[RepoRef(repo_id="demo/app", architecture="monolith")],
        risk_tier=RiskTier.LOW,
    )
    async with factory() as session:
        if await get_task(session, task.id) is None:
            await create_task(session, task)

        flash = GLMAdapter(model_id="glm-4.7-flash")
        full = GLMAdapter(model_id="glm-4.7")
        router = ModelRouter([flash, full])
        selected = router.select("implementation", "code_generation", {})
        print(
            f"router implementation/code_generation -> {selected.pricing.model_id} "
            f"score={selected.capability_score}"
        )
        design = router.select("design", "architecture", {})
        print(f"router design/architecture -> {design.pricing.model_id} score={design.capability_score}")

        sink = RecordingTelemetrySink()
        tracker = BudgetTracker(session)
        adapter = InstrumentedAdapter(
            selected,
            sink=sink,
            tracker=tracker,
            default_task_id=task.id,
            default_phase="implementation",
            default_agent_id="demo-phase02",
        )
        response = await adapter.acomplete(
            ModelRequest(
                messages=[
                    ChatMessage(role="user", content="Reply with exactly: hello from glm")
                ],
                task_id=task.id,
                phase="implementation",
                agent_id="demo-phase02",
                operation="code_generation",
            )
        )
        print("complete.content:", response.content)
        print("complete.usage:", response.usage.model_dump())
        print("llm_call spans:", json.dumps(sink.started, default=str))

        row = (
            await session.execute(
                select(CostTrackingRow)
                .where(CostTrackingRow.task_id == task.id)
                .order_by(CostTrackingRow.recorded_at.desc())
            )
        ).scalars().first()
        if row is None:
            print("no cost_tracking row", file=sys.stderr)
            await engine.dispose()
            return 1
        print(
            "cost_tracking:",
            json.dumps(
                {
                    "task_id": row.task_id,
                    "model_id": row.model_id,
                    "input_tokens": row.input_tokens,
                    "output_tokens": row.output_tokens,
                    "cost_usd": str(row.cost_usd),
                    "phase": row.phase,
                    "agent_id": row.agent_id,
                },
                indent=2,
            ),
        )
        print("budget:", (await tracker.check_budget(task.id)).value)

    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
