"""Pure budget threshold tests — no database."""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from common.budget import BudgetStatus, BudgetTracker, KillSwitchError, evaluate_budget


def test_evaluate_budget_within_limits_is_ok() -> None:
    assert (
        evaluate_budget(
            cost_usd=Decimal("0.50"),
            tokens=100,
            visits=2,
            cost_ceiling_usd=20.0,
            token_ceiling=2_000_000,
            max_node_visits=100,
        )
        is BudgetStatus.OK
    )


def test_evaluate_budget_cost_alone_exceeds() -> None:
    assert (
        evaluate_budget(
            cost_usd=Decimal("20.01"),
            tokens=1,
            visits=1,
            cost_ceiling_usd=20.0,
            token_ceiling=2_000_000,
            max_node_visits=100,
        )
        is BudgetStatus.EXCEEDED
    )


def test_evaluate_budget_tokens_alone_exceeds() -> None:
    assert (
        evaluate_budget(
            cost_usd=Decimal("0.01"),
            tokens=2_000_001,
            visits=1,
            cost_ceiling_usd=20.0,
            token_ceiling=2_000_000,
            max_node_visits=100,
        )
        is BudgetStatus.EXCEEDED
    )


def test_evaluate_budget_visits_alone_exceeds() -> None:
    assert (
        evaluate_budget(
            cost_usd=Decimal("0.01"),
            tokens=1,
            visits=101,
            cost_ceiling_usd=20.0,
            token_ceiling=2_000_000,
            max_node_visits=100,
        )
        is BudgetStatus.EXCEEDED
    )


def test_evaluate_budget_equal_to_ceiling_is_ok() -> None:
    assert (
        evaluate_budget(
            cost_usd=Decimal("20.0"),
            tokens=2_000_000,
            visits=100,
            cost_ceiling_usd=20.0,
            token_ceiling=2_000_000,
            max_node_visits=100,
        )
        is BudgetStatus.OK
    )


@pytest.mark.asyncio
async def test_check_budget_db_failure_is_fail_closed_exceeded() -> None:
    tracker = BudgetTracker(session=AsyncMock(), max_node_visits=10)
    tracker._check_budget_inner = AsyncMock(side_effect=RuntimeError("db unavailable"))  # type: ignore[method-assign]
    status = await tracker.check_budget("task-001")
    assert status is BudgetStatus.EXCEEDED


@pytest.mark.asyncio
async def test_enforce_budget_raises_kill_switch_on_exceeded() -> None:
    tracker = BudgetTracker(session=AsyncMock(), max_node_visits=10)
    tracker.check_budget = AsyncMock(return_value=BudgetStatus.EXCEEDED)  # type: ignore[method-assign]
    with pytest.raises(KillSwitchError) as exc_info:
        await tracker.enforce_budget("task-001")
    assert exc_info.value.task_id == "task-001"
