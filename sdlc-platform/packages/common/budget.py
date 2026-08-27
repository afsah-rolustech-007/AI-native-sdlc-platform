"""Per-task cost/token kill-switch (`final_plan.md` §B.7).

`record()` stores an already-computed `cost_usd`. Do not pass a model provider's
self-reported cost — Phase 02's pricing registry must compute the amount.

`check_budget()` never returns `ok` if the check itself fails (Fail-Closed).
Graph routing to `TaskState.BLOCKED` is Phase 01; this module only reports status
and raises `KillSwitchError` from `enforce_budget()`.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import get_settings
from common.models import CostTrackingRow, TaskRow


class BudgetStatus(str, Enum):
    OK = "ok"
    EXCEEDED = "exceeded"


class KillSwitchError(Exception):
    """Budget or visit ceiling was hit. Phase 01 should route the task to BLOCKED."""

    def __init__(self, task_id: str, reason: str) -> None:
        self.task_id = task_id
        self.reason = reason
        super().__init__(f"kill-switch for {task_id}: {reason}")


def evaluate_budget(
    *,
    cost_usd: Decimal,
    tokens: int,
    visits: int,
    cost_ceiling_usd: float,
    token_ceiling: int,
    max_node_visits: int,
) -> BudgetStatus:
    """Pure threshold check so unit tests need no database."""
    if cost_usd > Decimal(str(cost_ceiling_usd)):
        return BudgetStatus.EXCEEDED
    if tokens > token_ceiling:
        return BudgetStatus.EXCEEDED
    if visits > max_node_visits:
        return BudgetStatus.EXCEEDED
    return BudgetStatus.OK


class BudgetTracker:
    def __init__(
        self,
        session: AsyncSession,
        *,
        max_node_visits: int | None = None,
    ) -> None:
        self._session = session
        self._max_node_visits = (
            max_node_visits if max_node_visits is not None else get_settings().max_node_visits
        )

    async def record(
        self,
        task_id: str,
        phase: str,
        agent_id: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        *,
        idempotency_key: str | None = None,
        model_id: str | None = None,
        latency_ms: int | None = None,
    ) -> bool:
        """Write one `cost_tracking` row.

        Returns True if a row was inserted, False if `idempotency_key` was a duplicate.
        `cost_usd` must already be computed by our pricing (not the provider).
        """
        values = {
            "task_id": task_id,
            "phase": phase,
            "agent_id": agent_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": Decimal(str(cost_usd)),
            "model_id": model_id,
            "latency_ms": latency_ms,
            "idempotency_key": idempotency_key,
        }
        if idempotency_key is None:
            self._session.add(CostTrackingRow(**values))
            await self._session.commit()
            return True

        stmt = (
            insert(CostTrackingRow)
            .values(**values)
            .on_conflict_do_nothing(constraint="uq_cost_tracking_idempotency_key")
            .returning(CostTrackingRow.id)
        )
        result = await self._session.execute(stmt)
        inserted = result.scalar_one_or_none() is not None
        await self._session.commit()
        return inserted

    async def check_budget(self, task_id: str) -> BudgetStatus:
        """Sum spend/visits for `task_id`. Any internal error → `exceeded`."""
        try:
            return await self._check_budget_inner(task_id)
        except Exception:  # noqa: BLE001 — fail-closed: any check failure is exceeded
            return BudgetStatus.EXCEEDED

    async def enforce_budget(self, task_id: str) -> BudgetStatus:
        """Like `check_budget`, but raises `KillSwitchError` when exceeded."""
        status = await self.check_budget(task_id)
        if status is BudgetStatus.EXCEEDED:
            raise KillSwitchError(task_id, "budget or visit ceiling exceeded (fail-closed)")
        return status

    async def _check_budget_inner(self, task_id: str) -> BudgetStatus:
        task = await self._session.get(TaskRow, task_id)
        if task is None:
            raise KeyError(task_id)

        totals = await self._session.execute(
            select(
                func.coalesce(func.sum(CostTrackingRow.cost_usd), 0),
                func.coalesce(func.sum(CostTrackingRow.input_tokens), 0),
                func.coalesce(func.sum(CostTrackingRow.output_tokens), 0),
                func.count(CostTrackingRow.id),
            ).where(CostTrackingRow.task_id == task_id)
        )
        cost_usd, input_tokens, output_tokens, visits = totals.one()
        tokens = int(input_tokens) + int(output_tokens)
        cost_ceiling = float(task.cost_ceiling_usd if task.cost_ceiling_usd is not None else 20.0)
        token_ceiling = int(task.token_ceiling if task.token_ceiling is not None else 2_000_000)
        return evaluate_budget(
            cost_usd=Decimal(str(cost_usd)),
            tokens=tokens,
            visits=int(visits),
            cost_ceiling_usd=cost_ceiling,
            token_ceiling=token_ceiling,
            max_node_visits=self._max_node_visits,
        )
