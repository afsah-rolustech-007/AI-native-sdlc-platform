"""SQLAlchemy tables for the working-tree catalog, L1 symbols, and L3 embeddings.

These are RI-specific (not in `final_plan.md` §R). `alembic check` includes them
because `db/migrations/env.py` imports this module onto `common.models.Base`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from common.models import Base

# Must match vector.constants.EMBEDDING_DIMENSIONS and migration 0003.
EMBEDDING_DIMENSIONS = 2048


class PgVector(UserDefinedType):
    """pgvector `vector(N)` without importing a provider SDK or the pgvector Python extra.

    Bind/result processing is unused: inserts go through CAST(:embedding AS vector).
    """

    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **kwargs: object) -> str:
        return f"vector({self.dimensions})"


class IndexedFileRow(Base):
    """SHA-256 catalog of one eligible working-tree path. Hash is freshness authority."""

    __tablename__ = "indexed_files"
    __table_args__ = (
        CheckConstraint(
            "parse_status IN ('ok', 'skipped', 'parse_error')",
            name="indexed_files_parse_status_check",
        ),
    )

    repo_root: Mapped[str] = mapped_column(Text, primary_key=True)
    relative_path: Mapped[str] = mapped_column(Text, primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mtime_ns: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False)


class SymbolRow(Base):
    """Persisted L1 symbol. Body text is not stored; line ranges point at the working tree."""

    __tablename__ = "symbols"
    __table_args__ = (
        ForeignKeyConstraint(
            ["repo_root", "file_path"],
            ["indexed_files.repo_root", "indexed_files.relative_path"],
            ondelete="CASCADE",
            name="symbols_file_fk",
        ),
        Index("idx_symbols_file_path", "repo_root", "file_path"),
    )

    repo_root: Mapped[str] = mapped_column(Text, primary_key=True)
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    signature: Mapped[str | None] = mapped_column(Text)
    docstring: Mapped[str | None] = mapped_column(Text)


class RepoIndexSnapshotRow(Base):
    """Repo-level index metadata. `catalog_hash` is not a git commit SHA."""

    __tablename__ = "repo_index_snapshots"
    __table_args__ = (UniqueConstraint("repo_root", name="uq_repo_index_snapshots_repo_root"),)

    snapshot_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    repo_root: Mapped[str] = mapped_column(Text, nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    catalog_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class CodeEmbeddingRow(Base):
    """One L3 chunk vector. No FK to `symbols` or `indexed_files`.

    Section 05 deletes/reinserts `symbols` on every file modify. A CASCADE FK
    would wipe embeddings and force a re-embed of unchanged chunks. Identity is
    `(repo_root, symbol_id)`; `content_hash` is SHA-256 of `chunk_text`.
    """

    __tablename__ = "code_embeddings"
    __table_args__ = (Index("idx_code_embeddings_file_path", "repo_root", "file_path"),)

    repo_root: Mapped[str] = mapped_column(Text, primary_key=True)
    symbol_id: Mapped[str] = mapped_column(Text, primary_key=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[object] = mapped_column(PgVector(EMBEDDING_DIMENSIONS), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
