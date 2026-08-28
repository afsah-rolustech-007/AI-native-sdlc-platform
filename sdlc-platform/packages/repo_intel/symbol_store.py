"""Postgres helpers for the symbol catalog. Per-file replace is Section 05-ready."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from repo_intel.exceptions import FileNotIndexedError, StaleIndexError, SymbolNotFoundError
from repo_intel.indexers.catalog import FileSnapshot, sha256_bytes
from repo_intel.models import ParseStatus, Symbol
from repo_intel.tables import IndexedFileRow, RepoIndexSnapshotRow, SymbolRow


def _root_key(repo_root: Path) -> str:
    return str(repo_root)


def symbol_from_row(row: SymbolRow) -> Symbol:
    return Symbol(
        id=row.id,
        kind=row.kind,
        name=row.name,
        file_path=row.file_path,
        start_line=row.start_line,
        end_line=row.end_line,
        signature=row.signature,
        docstring=row.docstring,
    )


async def delete_repo_index(session: AsyncSession, repo_root: Path) -> None:
    """Drop catalog + symbols + snapshot for this working tree (CASCADE on symbols)."""
    key = _root_key(repo_root)
    await session.execute(
        delete(RepoIndexSnapshotRow).where(RepoIndexSnapshotRow.repo_root == key)
    )
    await session.execute(delete(IndexedFileRow).where(IndexedFileRow.repo_root == key))


async def delete_file_index(session: AsyncSession, repo_root: Path, relative_path: str) -> None:
    """Section 05 uses this for modify/delete of a single path."""
    await session.execute(
        delete(IndexedFileRow).where(
            IndexedFileRow.repo_root == _root_key(repo_root),
            IndexedFileRow.relative_path == relative_path,
        )
    )


async def insert_indexed_file(
    session: AsyncSession,
    repo_root: Path,
    snapshot: FileSnapshot,
    parse_status: ParseStatus,
) -> None:
    session.add(
        IndexedFileRow(
            repo_root=_root_key(repo_root),
            relative_path=snapshot.relative_path,
            content_hash=snapshot.content_hash,
            size_bytes=snapshot.size_bytes,
            mtime_ns=snapshot.mtime_ns,
            last_indexed_at=datetime.now(UTC),
            parse_status=parse_status,
        )
    )
    await session.flush()


async def insert_symbols(session: AsyncSession, repo_root: Path, symbols: list[Symbol]) -> None:
    if not symbols:
        return
    key = _root_key(repo_root)
    session.add_all(
        [
            SymbolRow(
                repo_root=key,
                id=symbol.id,
                kind=symbol.kind,
                name=symbol.name,
                file_path=symbol.file_path,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                signature=symbol.signature,
                docstring=symbol.docstring,
            )
            for symbol in symbols
        ]
    )
    await session.flush()


async def upsert_snapshot(
    session: AsyncSession, repo_root: Path, *, file_count: int, catalog_hash: str
) -> None:
    key = _root_key(repo_root)
    await session.execute(
        delete(RepoIndexSnapshotRow).where(RepoIndexSnapshotRow.repo_root == key)
    )
    session.add(
        RepoIndexSnapshotRow(
            repo_root=key,
            indexed_at=datetime.now(UTC),
            file_count=file_count,
            catalog_hash=catalog_hash,
        )
    )
    await session.flush()


async def get_indexed_file(
    session: AsyncSession, repo_root: Path, relative_path: str
) -> IndexedFileRow | None:
    result = await session.execute(
        select(IndexedFileRow).where(
            IndexedFileRow.repo_root == _root_key(repo_root),
            IndexedFileRow.relative_path == relative_path,
        )
    )
    return result.scalar_one_or_none()


async def get_symbol_row(
    session: AsyncSession, repo_root: Path, symbol_id: str
) -> SymbolRow | None:
    result = await session.execute(
        select(SymbolRow).where(
            SymbolRow.repo_root == _root_key(repo_root),
            SymbolRow.id == symbol_id,
        )
    )
    return result.scalar_one_or_none()


async def get_file_symbol_rows(
    session: AsyncSession, repo_root: Path, relative_path: str
) -> list[SymbolRow]:
    result = await session.execute(
        select(SymbolRow)
        .where(
            SymbolRow.repo_root == _root_key(repo_root),
            SymbolRow.file_path == relative_path,
        )
        .order_by(SymbolRow.start_line, SymbolRow.end_line, SymbolRow.id)
    )
    return list(result.scalars().all())


async def assert_file_fresh(
    session: AsyncSession, repo_root: Path, relative_path: str
) -> IndexedFileRow:
    """Fail closed if this path's working-tree SHA-256 differs from the catalog."""
    row = await get_indexed_file(session, repo_root, relative_path)
    if row is None:
        raise FileNotIndexedError(relative_path)
    disk_path = repo_root / relative_path
    if not disk_path.is_file():
        raise StaleIndexError([relative_path])
    current = sha256_bytes(disk_path.read_bytes())
    if current != row.content_hash:
        raise StaleIndexError([relative_path])
    return row


async def require_symbol(session: AsyncSession, repo_root: Path, symbol_id: str) -> Symbol:
    row = await get_symbol_row(session, repo_root, symbol_id)
    if row is None:
        raise SymbolNotFoundError(symbol_id)
    return symbol_from_row(row)
