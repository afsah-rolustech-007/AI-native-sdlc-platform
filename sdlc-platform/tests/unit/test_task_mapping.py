"""§B.1 Task ↔ §R row mapping (extra Pydantic fields are not stored)."""

from tests.factories import make_task

from common.task import TaskBudget, TaskState
from common.task_repository import row_to_task, task_to_row


def test_task_to_row_copies_section_r_columns() -> None:
    task = make_task(
        id="map-1",
        state=TaskState.DESIGN,
        budget=TaskBudget(token_ceiling=50_000, cost_ceiling_usd=1.5, max_retries_per_node=9),
    )
    row = task_to_row(task)
    assert row.id == "map-1"
    assert row.type == "feature"
    assert row.state == "design"
    assert row.token_ceiling == 50_000
    assert row.cost_ceiling_usd == 1.5
    assert row.created_by is None
    assert row.completed_at is None


def test_row_to_task_defaults_fields_absent_from_section_r() -> None:
    task = make_task(id="map-2")
    restored = row_to_task(task_to_row(task))
    assert restored.id == "map-2"
    assert restored.repo_refs == []
    assert restored.approvals == []
    assert restored.lineage == {}
    assert restored.artifact_refs == []
    assert restored.budget.max_retries_per_node == 3
