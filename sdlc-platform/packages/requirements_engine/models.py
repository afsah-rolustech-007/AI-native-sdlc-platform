"""Shared Phase 04 working types that are not claims (Question, AutoAnswer, events).

`evidence_plan` is validated by `plans.parse_evidence_plan` when the YAML loads.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from requirements_engine.claims import EpistemicStatus


class QuestionCategory(str, Enum):
    BUSINESS_OBJECTIVE = "business_objective"
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    SECURITY_COMPLIANCE = "security_compliance"
    PERFORMANCE = "performance"
    SCALABILITY = "scalability"
    RELIABILITY = "reliability"
    DATA_INTEGRITY = "data_integrity"
    API_CONTRACTS = "api_contracts"
    DEPLOYMENT_CONSTRAINTS = "deployment_constraints"


E4_CATEGORIES: frozenset[str] = frozenset(item.value for item in QuestionCategory)

_CATEGORY_DEFAULTS: dict[str, tuple[float, float, float]] = {
    QuestionCategory.BUSINESS_OBJECTIVE.value: (0.80, 0.40, 0.90),
    QuestionCategory.FUNCTIONAL.value: (0.70, 0.50, 0.70),
    QuestionCategory.NON_FUNCTIONAL.value: (0.50, 0.50, 0.50),
    QuestionCategory.SECURITY_COMPLIANCE.value: (0.90, 0.90, 0.80),
    QuestionCategory.PERFORMANCE.value: (0.60, 0.60, 0.50),
    QuestionCategory.SCALABILITY.value: (0.55, 0.55, 0.45),
    QuestionCategory.RELIABILITY.value: (0.60, 0.70, 0.50),
    QuestionCategory.DATA_INTEGRITY.value: (0.70, 0.75, 0.55),
    QuestionCategory.API_CONTRACTS.value: (0.65, 0.60, 0.50),
    QuestionCategory.DEPLOYMENT_CONSTRAINTS.value: (0.50, 0.55, 0.40),
}


class Question(BaseModel):
    id: str
    text: str
    category: str
    applies_if: dict[str, Any]
    depends_on: list[str] = Field(default_factory=list)
    mandatory: bool = False
    evidence_plan: dict[str, Any] | None = None
    impact: float = 0.5
    risk: float = 0.5
    information_value: float = 0.5
    # Gate for optional slots only. Never a divisor. Mandatory questions ignore this.
    asking_cost: float = 0.0
    render: str | None = None


class AutoAnswer(BaseModel):
    """Filled by Group C. Declared now so later groups do not reshape the contract."""

    slot_id: str
    answer: str
    evidence_refs: list[str] = Field(default_factory=list)
    status: Literal["fact", "inference"]
    confidence: Literal["low", "medium", "high"]


class SlotAnswer(BaseModel):
    question_id: str
    text: str
    source: Literal["human", "auto"] = "human"


class SessionEventKind(str, Enum):
    START = "start"
    EXTRACT = "extract"
    SNAPSHOT = "snapshot"
    CLASSIFY = "classify"
    ACTIVATE = "activate"
    SEED = "seed"
    RETRIEVE = "retrieve"
    AUTO_ANSWER = "auto_answer"
    RANK = "rank"
    ASK = "ask"
    ANSWER = "answer"
    SUFFICIENCY = "sufficiency"
    EXIT = "exit"


class SessionEvent(BaseModel):
    kind: SessionEventKind
    payload: dict[str, Any] = Field(default_factory=dict)


def category_defaults(category: str) -> tuple[float, float, float]:
    return _CATEGORY_DEFAULTS.get(category, (0.5, 0.5, 0.5))


def unanswered_status() -> EpistemicStatus:
    return EpistemicStatus.UNKNOWN
