"""SQLAlchemy tables for Phase 00. Column names follow `final_plan.md` §R.

Only four tables are created now: `tasks`, `cost_tracking`, `approvals`, and
`hitl_log`. ApprovalGate (Phase 05 §02) writes the latter two. Later §R tables
wait for their phases.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_state", "state"),
        Index("idx_tasks_risk_tier", "risk_tier"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    methodology: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    state: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'intake'")
    )
    workflow_profile_id: Mapped[str | None] = mapped_column(String(255))
    token_ceiling: Mapped[int | None] = mapped_column(Integer, server_default=text("2000000"))
    cost_ceiling_usd: Mapped[float | None] = mapped_column(Float, server_default=text("20.0"))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    # Present on §R, not on the Pydantic Task — left null until a later phase writes it.
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(String(255))


class ApprovalRow(Base):
    """Written by ApprovalGate (Phase 05 §02) on a human decision."""

    __tablename__ = "approvals"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    task_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("tasks.id"))
    checkpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    approver: Mapped[str | None] = mapped_column(String(255))
    decision: Mapped[str | None] = mapped_column(String(50))
    evidence_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HitlLogRow(Base):
    """Durable HITL inbox (§D.7.1). ApprovalGate writes rows; UI reads pending here."""

    __tablename__ = "hitl_log"
    __table_args__ = (
        CheckConstraint(
            "request_type IN ('clarification', 'approval', 'policy_review', 'risk_approval')",
            name="hitl_log_request_type_check",
        ),
        Index(
            "idx_hitl_request_type",
            "request_type",
            postgresql_where=text("responded_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    task_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("tasks.id"))
    request_type: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'approval'")
    )
    phase: Mapped[str | None] = mapped_column(String(100))
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_ref: Mapped[str | None] = mapped_column(Text)
    options: Mapped[dict | None] = mapped_column(JSONB)
    response: Mapped[str | None] = mapped_column(Text)
    responded_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timeout_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CostTrackingRow(Base):
    __tablename__ = "cost_tracking"
    __table_args__ = (
        Index("idx_cost_task_id", "task_id"),
        # Not in §R. Required by Phase 00 §03 (retry-safe writes). See migration comment.
        UniqueConstraint("idempotency_key", name="uq_cost_tracking_idempotency_key"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    task_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("tasks.id"))
    agent_id: Mapped[str | None] = mapped_column(String(255))
    phase: Mapped[str | None] = mapped_column(String(100))
    model_id: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
