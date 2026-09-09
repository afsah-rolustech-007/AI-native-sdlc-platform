"""Add code_embeddings (pgvector L3).

Revision ID: 0003_add_code_embeddings
Revises: 0002_add_symbol_catalog
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from repo_intel.tables import EMBEDDING_DIMENSIONS, PgVector

revision: str = "0003_add_code_embeddings"
down_revision: Union[str, Sequence[str], None] = "0002_add_symbol_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "code_embeddings",
        sa.Column("repo_root", sa.Text(), nullable=False),
        sa.Column("symbol_id", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", PgVector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("repo_root", "symbol_id"),
    )
    op.create_index(
        "idx_code_embeddings_file_path",
        "code_embeddings",
        ["repo_root", "file_path"],
    )


def downgrade() -> None:
    op.drop_index("idx_code_embeddings_file_path", table_name="code_embeddings")
    op.drop_table("code_embeddings")
