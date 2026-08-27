"""Task persistence against real Postgres + Alembic."""

from tests.factories import make_task

from common.task import TaskBudget, TaskState
from common.task_repository import create_task, get_task, update_task_state


async def test_create_and_get_task_round_trip_persisted_fields(db_session) -> None:
    original = make_task(
        id="persist-1",
        title="Persist me",
        budget=TaskBudget(token_ceiling=99_000, cost_ceiling_usd=3.25),
    )
    stored = await create_task(db_session, original)
    loaded = await get_task(db_session, "persist-1")
    assert loaded is not None
    assert loaded.id == stored.id == "persist-1"
    assert loaded.title == "Persist me"
    assert loaded.type == original.type
    assert loaded.methodology == original.methodology
    assert loaded.risk_tier == original.risk_tier
    assert loaded.state is TaskState.INTAKE
    assert loaded.budget.token_ceiling == 99_000
    assert loaded.budget.cost_ceiling_usd == 3.25
    assert loaded.source == "user_request"


async def test_get_task_returns_none_when_missing(db_session) -> None:
    assert await get_task(db_session, "does-not-exist") is None


async def test_update_task_state_writes_blocked(db_session) -> None:
    await create_task(db_session, make_task(id="persist-2"))
    updated = await update_task_state(db_session, "persist-2", TaskState.BLOCKED)
    assert updated.state is TaskState.BLOCKED
    reloaded = await get_task(db_session, "persist-2")
    assert reloaded is not None
    assert reloaded.state is TaskState.BLOCKED
