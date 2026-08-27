"""BudgetTracker against real cost_tracking rows."""

from tests.factories import make_task

from common.budget import BudgetStatus, BudgetTracker, KillSwitchError
from common.task import TaskBudget
from common.task_repository import create_task


async def test_check_budget_sums_multiple_records(db_session) -> None:
    await create_task(
        db_session,
        make_task(id="bud-sum", budget=TaskBudget(cost_ceiling_usd=1.0, token_ceiling=10_000)),
    )
    tracker = BudgetTracker(db_session, max_node_visits=50)
    await tracker.record("bud-sum", "intake", "sim-1", 100, 50, 0.20, idempotency_key="k1")
    await tracker.record("bud-sum", "intake", "sim-1", 100, 50, 0.20, idempotency_key="k2")
    assert await tracker.check_budget("bud-sum") is BudgetStatus.OK
    await tracker.record("bud-sum", "intake", "sim-1", 100, 50, 0.70, idempotency_key="k3")
    assert await tracker.check_budget("bud-sum") is BudgetStatus.EXCEEDED


async def test_cost_ceiling_exceeded_independently_of_tokens(db_session) -> None:
    await create_task(
        db_session,
        make_task(id="bud-cost", budget=TaskBudget(cost_ceiling_usd=0.01, token_ceiling=10_000_000)),
    )
    tracker = BudgetTracker(db_session, max_node_visits=50)
    await tracker.record("bud-cost", "intake", "sim", 1, 1, 0.02, idempotency_key="c1")
    assert await tracker.check_budget("bud-cost") is BudgetStatus.EXCEEDED


async def test_token_ceiling_exceeded_independently_of_cost(db_session) -> None:
    await create_task(
        db_session,
        make_task(id="bud-tok", budget=TaskBudget(cost_ceiling_usd=100.0, token_ceiling=10)),
    )
    tracker = BudgetTracker(db_session, max_node_visits=50)
    await tracker.record("bud-tok", "intake", "sim", 8, 8, 0.001, idempotency_key="t1")
    assert await tracker.check_budget("bud-tok") is BudgetStatus.EXCEEDED


async def test_visit_ceiling_exceeded_independently(db_session) -> None:
    await create_task(
        db_session,
        make_task(id="bud-vis", budget=TaskBudget(cost_ceiling_usd=100.0, token_ceiling=10_000_000)),
    )
    tracker = BudgetTracker(db_session, max_node_visits=2)
    await tracker.record("bud-vis", "intake", "sim", 1, 1, 0.0, idempotency_key="v1")
    await tracker.record("bud-vis", "intake", "sim", 1, 1, 0.0, idempotency_key="v2")
    assert await tracker.check_budget("bud-vis") is BudgetStatus.OK
    await tracker.record("bud-vis", "intake", "sim", 1, 1, 0.0, idempotency_key="v3")
    assert await tracker.check_budget("bud-vis") is BudgetStatus.EXCEEDED


async def test_duplicate_idempotency_key_does_not_double_count(db_session) -> None:
    await create_task(
        db_session,
        make_task(id="bud-idemp", budget=TaskBudget(cost_ceiling_usd=0.15, token_ceiling=10_000)),
    )
    tracker = BudgetTracker(db_session, max_node_visits=50)
    first = await tracker.record(
        "bud-idemp", "intake", "sim", 1, 1, 0.10, idempotency_key="same-key"
    )
    second = await tracker.record(
        "bud-idemp", "intake", "sim", 1, 1, 0.10, idempotency_key="same-key"
    )
    assert first is True
    assert second is False
    assert await tracker.check_budget("bud-idemp") is BudgetStatus.OK


async def test_enforce_budget_raises_after_ceiling(db_session) -> None:
    await create_task(
        db_session,
        make_task(id="bud-kill", budget=TaskBudget(cost_ceiling_usd=0.01, token_ceiling=10_000)),
    )
    tracker = BudgetTracker(db_session, max_node_visits=50)
    await tracker.record("bud-kill", "intake", "sim", 1, 1, 1.0, idempotency_key="kill")
    try:
        await tracker.enforce_budget("bud-kill")
        raise AssertionError("expected KillSwitchError")
    except KillSwitchError as exc:
        assert exc.task_id == "bud-kill"
