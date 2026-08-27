"""Section 03 demo: record simulated cost until check_budget flips to exceeded.

Requires a migrated database (same as demo_section02).
Run from sdlc-platform/:  PYTHONPATH=packages python scripts/demo_section03.py
"""

import asyncio

from common.budget import BudgetTracker
from common.config import get_settings
from common.db import make_async_engine, make_session_factory
from common.task import Methodology, RepoRef, RiskTier, Task, TaskBudget, WorkType
from common.task_repository import create_task


async def main() -> None:
    settings = get_settings()
    engine = make_async_engine(settings.database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        task = Task(
            id="demo-section03",
            title="Section 03 budget demo",
            source="user_request",
            type=WorkType.FEATURE,
            methodology=Methodology.AGILE,
            repo_refs=[RepoRef(repo_id="demo/app", architecture="monolith")],
            risk_tier=RiskTier.LOW,
            budget=TaskBudget(cost_ceiling_usd=0.05, token_ceiling=1_000_000),
        )
        await create_task(session, task)
        tracker = BudgetTracker(session, max_node_visits=50)
        for i in range(1, 6):
            await tracker.record(
                task.id,
                "intake",
                "sim-agent",
                input_tokens=10,
                output_tokens=10,
                cost_usd=0.02,
                idempotency_key=f"demo-section03-{i}",
            )
            status = await tracker.check_budget(task.id)
            print(f"after record {i}: {status.value}")
            if status.value == "exceeded":
                break
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
