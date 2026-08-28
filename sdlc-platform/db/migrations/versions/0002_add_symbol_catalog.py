"""Add indexed_files, symbols, and repo_index_snapshots.

Revision ID: 0002_add_symbol_catalog
Revises: 0001_phase00_foundations
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_add_symbol_catalog"
down_revision: Union[str, Sequence[str], None] = "0001_phase00_foundations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "indexed_files",
        sa.Column("repo_root", sa.Text(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mtime_ns", sa.BigInteger(), nullable=False),
        sa.Column(
            "last_indexed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("parse_status", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("repo_root", "relative_path"),
        sa.CheckConstraint(
            "parse_status IN ('ok', 'skipped', 'parse_error')",
            name="indexed_files_parse_status_check",
        ),
    )

    op.create_table(
        "symbols",
        sa.Column("repo_root", sa.Text(), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("docstring", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("repo_root", "id"),
        sa.ForeignKeyConstraint(
            ["repo_root", "file_path"],
            ["indexed_files.repo_root", "indexed_files.relative_path"],
            ondelete="CASCADE",
            name="symbols_file_fk",
        ),
    )
    op.create_index("idx_symbols_file_path", "symbols", ["repo_root", "file_path"])

    op.create_table(
        "repo_index_snapshots",
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("repo_root", sa.Text(), nullable=False),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("catalog_hash", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("repo_root", name="uq_repo_index_snapshots_repo_root"),
    )


def downgrade() -> None:
    op.drop_table("repo_index_snapshots")
    op.drop_index("idx_symbols_file_path", table_name="symbols")
    op.drop_table("symbols")
    op.drop_table("indexed_files")
