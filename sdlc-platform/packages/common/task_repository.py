"""Persist `Task` to the `tasks` table (§R).

§B.1 has fields the SQL table does not (`repo_refs`, `lineage`, `artifact_refs`,
`approvals`, `budget.max_retries_per_node`). Those are not stored here — adding
columns would violate the §R match required by Section 02. Reloaded Tasks get
empty/default values for the missing fields.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models import TaskRow
from common.task import Methodology, RiskTier, Task, TaskBudget, TaskState, WorkType


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def task_to_row(task: Task) -> TaskRow:
    """Map Pydantic Task → §R columns. Extra Pydantic fields are dropped on purpose."""
    return TaskRow(
        id=task.id,
        title=task.title,
        source=task.source,
        type=task.type.value,
        methodology=task.methodology.value,
        risk_tier=task.risk_tier.value,
        confidence_score=task.confidence_score,
        state=task.state.value,
        workflow_profile_id=task.workflow_profile_id,
        token_ceiling=task.budget.token_ceiling,
        cost_ceiling_usd=task.budget.cost_ceiling_usd,
        created_at=_as_utc(task.created_at),
        completed_at=None,
        created_by=None,
    )


def row_to_task(row: TaskRow) -> Task:
    """Map §R columns → Pydantic Task. Non-§R fields use §B.1 defaults."""
    created = row.created_at or datetime.now(UTC)
    return Task(
        id=row.id,
        title=row.title,
        source=row.source,
        type=WorkType(row.type),
        methodology=Methodology(row.methodology),
        repo_refs=[],
        risk_tier=RiskTier(row.risk_tier),
        confidence_score=row.confidence_score if row.confidence_score is not None else 0.0,
        state=TaskState(row.state),
        workflow_profile_id=row.workflow_profile_id,
        budget=TaskBudget(
            token_ceiling=row.token_ceiling if row.token_ceiling is not None else 2_000_000,
            cost_ceiling_usd=(
                row.cost_ceiling_usd if row.cost_ceiling_usd is not None else 20.0
            ),
            max_retries_per_node=3,
        ),
        approvals=[],
        lineage={},
        artifact_refs=[],
        created_at=created,
    )


async def create_task(session: AsyncSession, task: Task) -> Task:
    """Insert `task` and return the stored record (reconstructed from §R columns)."""
    session.add(task_to_row(task))
    await session.commit()
    loaded = await get_task(session, task.id)
    if loaded is None:
        raise RuntimeError(f"task {task.id!r} missing after insert")
    return loaded


async def get_task(session: AsyncSession, task_id: str) -> Task | None:
    """Load a task by id, or None if it does not exist."""
    row = await session.get(TaskRow, task_id)
    if row is None:
        return None
    return row_to_task(row)


async def update_task_state(session: AsyncSession, task_id: str, state: TaskState) -> Task:
    """Set Postgres `tasks.state` and return the updated Task."""
    result = await session.execute(select(TaskRow).where(TaskRow.id == task_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(task_id)
    row.state = state.value
    await session.commit()
    return row_to_task(row)
