"""Add kind, chunk_tokens, truncated to code_embeddings.

Revision ID: 0004_code_embeddings_metadata
Revises: 0003_add_code_embeddings
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_code_embeddings_metadata"
down_revision: Union[str, Sequence[str], None] = "0003_add_code_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "code_embeddings",
        sa.Column("kind", sa.String(length=50), nullable=False, server_default="function"),
    )
    op.add_column(
        "code_embeddings",
        sa.Column("chunk_tokens", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "code_embeddings",
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("code_embeddings", "kind", server_default=None)
    op.alter_column("code_embeddings", "chunk_tokens", server_default=None)


def downgrade() -> None:
    op.drop_column("code_embeddings", "truncated")
    op.drop_column("code_embeddings", "chunk_tokens")
    op.drop_column("code_embeddings", "kind")
