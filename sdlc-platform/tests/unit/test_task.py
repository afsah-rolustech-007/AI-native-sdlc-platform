"""Section 01 unit tests: enums, id length, Pydantic round-trip.

Postgres round-trip is a Section 02 integration test (`task_repository.get_task`).
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from common.task import (
    ApprovalRecord,
    Methodology,
    RepoRef,
    RiskTier,
    Task,
    TaskBudget,
    TaskState,
    WorkType,
)


def _minimal_task(**overrides) -> Task:
    """Build a valid Task with only the fields §B.1 requires at construction time."""
    fields = {
        "id": "task-001",
        "title": "Add login",
        "source": "user_request",
        "type": WorkType.FEATURE,
        "methodology": Methodology.AGILE,
        "repo_refs": [RepoRef(repo_id="demo/app", architecture="monolith")],
        "risk_tier": RiskTier.LOW,
    }
    fields.update(overrides)
    return Task(**fields)


def test_every_work_type_member_constructs() -> None:
    assert {m.value for m in WorkType} == {
        "new_project",
        "feature",
        "bug",
        "hotfix",
        "refactor",
        "migration",
        "tech_debt",
        "maintenance",
    }
    for member in WorkType:
        assert WorkType(member.value) is member


def test_every_methodology_member_constructs() -> None:
    assert {m.value for m in Methodology} == {"agile", "waterfall", "hybrid"}
    for member in Methodology:
        assert Methodology(member.value) is member


def test_every_risk_tier_member_constructs() -> None:
    assert {m.value for m in RiskTier} == {"low", "medium", "high", "critical"}
    for member in RiskTier:
        assert RiskTier(member.value) is member


def test_every_task_state_member_constructs() -> None:
    assert {m.value for m in TaskState} == {
        "intake",
        "requirements",
        "design",
        "implementation",
        "qa",
        "review",
        "release",
        "monitoring",
        "done",
        "blocked",
    }
    for member in TaskState:
        assert TaskState(member.value) is member


def test_task_rejects_id_longer_than_255_chars() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _minimal_task(id="x" * 256)
    assert "id" in str(exc_info.value)


def test_task_accepts_id_of_exactly_255_chars() -> None:
    task = _minimal_task(id="y" * 255)
    assert len(task.id) == 255


def test_task_round_trips_through_dump_and_validate_without_field_loss() -> None:
    created = datetime(2026, 8, 27, 8, 0, 0, tzinfo=UTC)
    approval = ApprovalRecord(
        checkpoint="scope",
        approver="reviewer@example.com",
        decision="approve",
        evidence_ref="bb://approvals/1",
        timestamp=created,
    )
    original = _minimal_task(
        confidence_score=0.4,
        state=TaskState.REQUIREMENTS,
        workflow_profile_id="conservative",
        budget=TaskBudget(
            token_ceiling=1_000_000,
            cost_ceiling_usd=10.0,
            max_retries_per_node=2,
        ),
        approvals=[approval],
        lineage={"parent_task_id": "task-000"},
        artifact_refs=["bb://reqs/1"],
        created_at=created,
    )

    dumped = original.model_dump()
    restored = Task.model_validate(dumped)

    assert dumped.keys() == original.model_dump().keys()
    assert restored == original
    assert restored.repo_refs[0].repo_id == "demo/app"
    assert restored.approvals[0].decision == "approve"
    assert restored.lineage == {"parent_task_id": "task-000"}
    assert restored.artifact_refs == ["bb://reqs/1"]


def test_task_budget_defaults_match_section_b1() -> None:
    task = _minimal_task()
    assert task.budget.token_ceiling == 2_000_000
    assert task.budget.cost_ceiling_usd == 20.0
    assert task.budget.max_retries_per_node == 3
    assert task.state is TaskState.INTAKE
    assert task.confidence_score == 0.0
    assert task.workflow_profile_id is None
    assert task.approvals == []
    assert task.lineage == {}
    assert task.artifact_refs == []
