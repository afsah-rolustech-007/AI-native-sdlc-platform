"""Phase 00 initial schema: tasks, cost_tracking, approvals, hitl_log.

Revision ID: 0001_phase00_foundations
Revises:
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_phase00_foundations"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("methodology", sa.String(length=50), nullable=False),
        sa.Column("risk_tier", sa.String(length=20), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column(
            "state",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'intake'"),
        ),
        sa.Column("workflow_profile_id", sa.String(length=255), nullable=True),
        sa.Column("token_ceiling", sa.Integer(), server_default=sa.text("2000000")),
        sa.Column("cost_ceiling_usd", sa.Float(), server_default=sa.text("20.0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
    )
    op.create_index("idx_tasks_state", "tasks", ["state"])
    op.create_index("idx_tasks_risk_tier", "tasks", ["risk_tier"])

    op.create_table(
        "approvals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("task_id", sa.String(length=255), sa.ForeignKey("tasks.id")),
        sa.Column("checkpoint", sa.String(length=100), nullable=False),
        sa.Column("approver", sa.String(length=255), nullable=True),
        sa.Column("decision", sa.String(length=50), nullable=True),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "hitl_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("task_id", sa.String(length=255), sa.ForeignKey("tasks.id")),
        sa.Column(
            "request_type",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'approval'"),
        ),
        sa.Column("phase", sa.String(length=100), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("responded_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timeout_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "request_type IN ('clarification', 'approval', 'policy_review', 'risk_approval')",
            name="hitl_log_request_type_check",
        ),
    )
    op.create_index(
        "idx_hitl_request_type",
        "hitl_log",
        ["request_type"],
        postgresql_where=sa.text("responded_at IS NULL"),
    )

    op.create_table(
        "cost_tracking",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("task_id", sa.String(length=255), sa.ForeignKey("tasks.id")),
        sa.Column("agent_id", sa.String(length=255), nullable=True),
        sa.Column("phase", sa.String(length=100), nullable=True),
        sa.Column("model_id", sa.String(length=100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        # Not in §R. Phase 00 §03 requires retry-safe writes (anticipates §J.3).
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
    )
    op.create_index("idx_cost_task_id", "cost_tracking", ["task_id"])
    op.create_unique_constraint(
        "uq_cost_tracking_idempotency_key", "cost_tracking", ["idempotency_key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_cost_tracking_idempotency_key", "cost_tracking", type_="unique")
    op.drop_index("idx_cost_task_id", table_name="cost_tracking")
    op.drop_table("cost_tracking")
    op.drop_index("idx_hitl_request_type", table_name="hitl_log")
    op.drop_table("hitl_log")
    op.drop_table("approvals")
    op.drop_index("idx_tasks_risk_tier", table_name="tasks")
    op.drop_index("idx_tasks_state", table_name="tasks")
    op.drop_table("tasks")
