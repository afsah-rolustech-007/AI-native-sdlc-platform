"""Shared Task constructor for tests."""

from common.task import Methodology, RepoRef, RiskTier, Task, WorkType


def make_task(**overrides) -> Task:
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
