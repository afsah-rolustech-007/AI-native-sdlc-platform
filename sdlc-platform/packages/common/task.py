"""Task data model — `final_plan.md` §B.1.

Task is the durable record of one unit of work. It is a Pydantic model so invalid
data is rejected at runtime (TypedDict would only fail at type-check time).

No routing or policy logic belongs here. Field validation only. `Task.budget`
keeps these defaults until Phase 10's workflow engine may override cost.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class WorkType(str, Enum):
    """What kind of work this task is. Other phases match on these exact values."""

    NEW_PROJECT = "new_project"
    FEATURE = "feature"
    BUG = "bug"
    HOTFIX = "hotfix"
    REFACTOR = "refactor"
    MIGRATION = "migration"
    TECH_DEBT = "tech_debt"
    MAINTENANCE = "maintenance"


class Methodology(str, Enum):
    AGILE = "agile"
    WATERFALL = "waterfall"
    HYBRID = "hybrid"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskState(str, Enum):
    """SDLC phase (plus terminal DONE / BLOCKED). Postgres `tasks.state` stores this."""

    INTAKE = "intake"
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    IMPLEMENTATION = "implementation"
    QA = "qa"
    REVIEW = "review"
    RELEASE = "release"
    MONITORING = "monitoring"
    DONE = "done"
    BLOCKED = "blocked"


class RepoRef(BaseModel):
    repo_id: str
    architecture: str  # monolith | modular_monolith | microservices
    domain_shard: Optional[str] = None  # Which RI shard this task touches (§G.4)


class TaskBudget(BaseModel):
    token_ceiling: int = 2_000_000  # Total tokens across all agents for this task
    cost_ceiling_usd: float = 20.0
    max_retries_per_node: int = 3


class ApprovalRecord(BaseModel):
    checkpoint: str
    approver: str
    # Allowed values per §B.1: approve | reject_with_feedback | request_changes
    decision: str
    evidence_ref: str  # Blackboard pointer, not inlined
    timestamp: datetime


class Task(BaseModel):
    # Same 255-char cap as Postgres VARCHAR(255) and LangGraph thread_id truncation.
    id: str = Field(max_length=255)
    title: str
    source: str  # user_request | ticket_import | monitoring_incident | maintenance_scan
    type: WorkType
    methodology: Methodology
    repo_refs: list[RepoRef]
    risk_tier: RiskTier
    confidence_score: float = 0.0  # Computed by Confidence Model (§B.4)
    state: TaskState = TaskState.INTAKE
    workflow_profile_id: Optional[str] = None  # Set by Workflow Policy Engine (§F)
    budget: TaskBudget = Field(default_factory=TaskBudget)
    approvals: list[ApprovalRecord] = Field(default_factory=list)
    lineage: dict = Field(default_factory=dict)  # {parent_task_id?, root_incident_id?}
    artifact_refs: list[str] = Field(default_factory=list)  # Blackboard pointers
    created_at: datetime = Field(default_factory=datetime.utcnow)
