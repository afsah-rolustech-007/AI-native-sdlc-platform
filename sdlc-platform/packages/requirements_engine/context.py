"""Phase-04 WorkflowContext subset. Phase 10 §F.2 supersedes this.

Every flag is `T | None` with None = unknown. Unknown is not False.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from common.task import RiskTier, WorkType
from requirements_engine.claims import ClaimSet

CONTEXT_FLAG_FIELDS = (
    "touches_auth",
    "touches_pii",
    "touches_payments",
    "has_database_changes",
)

_AUTH_HINTS = ("auth", "authentication", "jwt", "oauth", "login", "sso", "oidc")
_PII_HINTS = ("pii", "gdpr", "personal data", "personally identifiable")
_PAY_HINTS = ("payment", "payments", "pci", "stripe", "billing charge")
_DB_HINTS = ("database", "migration", "schema change", "postgres", "mongodb", "sql")


class WorkflowContext(BaseModel):
    """Temporary predicate context. Do not treat this as the Phase 10 schema."""

    work_type: WorkType | None = None
    risk_tier: RiskTier | None = None
    touches_auth: bool | None = None
    touches_pii: bool | None = None
    touches_payments: bool | None = None
    has_database_changes: bool | None = None
    repo_architecture: str | None = None
    affected_modules: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


def apply_context_updates(context: WorkflowContext, updates: dict[str, Any]) -> WorkflowContext:
    """Apply explicit engineer/test updates. Unknown keys fail closed."""
    allowed = set(WorkflowContext.model_fields) - {"extra"}
    unknown = set(updates) - allowed
    if unknown:
        raise ValueError(f"unknown WorkflowContext fields: {sorted(unknown)}")
    return context.model_copy(update=updates)


def apply_claim_hints(context: WorkflowContext, claim_set: ClaimSet) -> WorkflowContext:
    """Fill None flags from claims. Never override an explicit False/True."""
    updates: dict[str, Any] = {}
    for claim in claim_set.claims:
        if claim.touches_auth is True:
            _fill_none(context, updates, "touches_auth", True)
        if claim.touches_pii is True:
            _fill_none(context, updates, "touches_pii", True)
        if claim.touches_payments is True:
            _fill_none(context, updates, "touches_payments", True)
        if claim.has_database_changes is True:
            _fill_none(context, updates, "has_database_changes", True)
        lowered = claim.text.lower()
        if any(hint in lowered for hint in _AUTH_HINTS):
            _fill_none(context, updates, "touches_auth", True)
        if any(hint in lowered for hint in _PII_HINTS):
            _fill_none(context, updates, "touches_pii", True)
        if any(hint in lowered for hint in _PAY_HINTS):
            _fill_none(context, updates, "touches_payments", True)
        if any(hint in lowered for hint in _DB_HINTS):
            _fill_none(context, updates, "has_database_changes", True)
    return apply_context_updates(context, updates) if updates else context


def _fill_none(
    context: WorkflowContext, updates: dict[str, Any], field: str, value: bool
) -> None:
    current = getattr(context, field)
    if current is None and field not in updates:
        updates[field] = value
