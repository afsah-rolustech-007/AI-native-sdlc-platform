"""Low-level SQL for the `code_embeddings` table.

PgvectorClient calls these helpers; search code usually should not import here.

Similarity: pgvector `<=>` is cosine distance (smaller = closer).
We expose score as `1 - distance` so higher = better match.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from repo_intel.models import CodeChunk
from repo_intel.vector.constants import WRITE_BATCH_SIZE

_INSERT = """
INSERT INTO code_embeddings (
    repo_root, symbol_id, file_path, kind, chunk_text,
    embedding, content_hash, start_line, end_line, chunk_tokens, truncated
) VALUES (
    :repo_root, :symbol_id, :file_path, :kind, :chunk_text,
    CAST(:embedding AS vector), :content_hash, :start_line, :end_line,
    :chunk_tokens, :truncated
)
"""

_UPSERT = (
    _INSERT
    + """
ON CONFLICT (repo_root, symbol_id) DO UPDATE SET
    file_path = EXCLUDED.file_path,
    kind = EXCLUDED.kind,
    chunk_text = EXCLUDED.chunk_text,
    embedding = EXCLUDED.embedding,
    content_hash = EXCLUDED.content_hash,
    start_line = EXCLUDED.start_line,
    end_line = EXCLUDED.end_line,
    chunk_tokens = EXCLUDED.chunk_tokens,
    truncated = EXCLUDED.truncated
"""
)

_HASHES = """
SELECT symbol_id, content_hash
FROM code_embeddings
WHERE repo_root = :repo_root AND file_path = :file_path
"""

_HASHES_REPO = """
SELECT file_path, symbol_id, content_hash
FROM code_embeddings
WHERE repo_root = :repo_root
"""


def format_vector(values: Sequence[float]) -> str:
    """Turn [0.1, 0.2, ...] into the string Postgres expects for CAST(... AS vector)."""
    return "[" + ",".join(str(float(x)) for x in values) + "]"


def _row_params(repo_root: str, chunk: CodeChunk, vector: Sequence[float]) -> dict[str, object]:
    if not chunk.symbol_id:
        raise ValueError("code_embeddings rows require a symbol_id")
    return {
        "repo_root": repo_root,
        "symbol_id": chunk.symbol_id,
        "file_path": chunk.file_path,
        "kind": chunk.kind,
        "chunk_text": chunk.chunk_text,
        "embedding": format_vector(vector),
        "content_hash": chunk.content_hash,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "chunk_tokens": chunk.chunk_tokens,
        "truncated": chunk.truncated,
    }


async def delete_repo_embeddings(session: AsyncSession, repo_root: str) -> None:
    await session.execute(
        text("DELETE FROM code_embeddings WHERE repo_root = :repo_root"),
        {"repo_root": repo_root},
    )


async def delete_file_embeddings(session: AsyncSession, repo_root: str, file_path: str) -> None:
    await session.execute(
        text("DELETE FROM code_embeddings WHERE repo_root = :repo_root AND file_path = :file_path"),
        {"repo_root": repo_root, "file_path": file_path},
    )


async def delete_missing_symbol_embeddings(
    session: AsyncSession,
    repo_root: str,
    file_path: str,
    keep_symbol_ids: set[str],
) -> None:
    """Delete embedding rows for symbols that were removed from the file."""
    if not keep_symbol_ids:
        await delete_file_embeddings(session, repo_root, file_path)
        return
    stmt = text(
        """
        DELETE FROM code_embeddings
        WHERE repo_root = :repo_root AND file_path = :file_path
          AND symbol_id NOT IN :keep_ids
        """
    ).bindparams(bindparam("keep_ids", expanding=True))
    await session.execute(
        stmt,
        {
            "repo_root": repo_root,
            "file_path": file_path,
            "keep_ids": list(keep_symbol_ids),
        },
    )


async def hashes_for_file(session: AsyncSession, repo_root: str, file_path: str) -> dict[str, str]:
    result = await session.execute(text(_HASHES), {"repo_root": repo_root, "file_path": file_path})
    return {str(row.symbol_id): str(row.content_hash) for row in result}


async def hashes_for_repo(session: AsyncSession, repo_root: str) -> dict[str, dict[str, str]]:
    """Return {file_path: {symbol_id: content_hash}} for the working tree."""
    result = await session.execute(text(_HASHES_REPO), {"repo_root": repo_root})
    by_file: dict[str, dict[str, str]] = {}
    for row in result:
        by_file.setdefault(str(row.file_path), {})[str(row.symbol_id)] = str(row.content_hash)
    return by_file


async def count_embeddings(session: AsyncSession, repo_root: str) -> int:
    result = await session.execute(
        text("SELECT COUNT(*) FROM code_embeddings WHERE repo_root = :repo_root"),
        {"repo_root": repo_root},
    )
    return int(result.scalar_one())


async def _execute_batches(
    session: AsyncSession,
    sql: str,
    repo_root: str,
    rows: list[tuple[CodeChunk, Sequence[float]]],
) -> None:
    params = [_row_params(repo_root, chunk, vector) for chunk, vector in rows]
    for start in range(0, len(params), WRITE_BATCH_SIZE):
        batch = params[start : start + WRITE_BATCH_SIZE]
        await session.execute(text(sql), batch)


async def insert_embeddings(
    session: AsyncSession,
    repo_root: str,
    rows: list[tuple[CodeChunk, Sequence[float]]],
) -> None:
    """Write new rows only — caller must delete old rows first on full rebuild."""
    if not rows:
        return
    await _execute_batches(session, _INSERT, repo_root, rows)


async def upsert_embeddings(
    session: AsyncSession,
    repo_root: str,
    rows: list[tuple[CodeChunk, Sequence[float]]],
) -> None:
    """Insert new chunks or update existing ones (same repo_root + symbol_id)."""
    if not rows:
        return
    await _execute_batches(session, _UPSERT, repo_root, rows)


def _chunk_from_row(row: Any) -> CodeChunk:
    return CodeChunk(
        symbol_id=str(row.symbol_id),
        file_path=str(row.file_path),
        kind=str(row.kind),
        chunk_text=str(row.chunk_text),
        content_hash=str(row.content_hash),
        start_line=int(row.start_line),
        end_line=int(row.end_line),
        chunk_tokens=int(row.chunk_tokens),
        truncated=bool(row.truncated),
        score=float(row.score),
    )


async def cosine_search(
    session: AsyncSession,
    repo_root: str,
    query_vector: Sequence[float],
    top_k: int,
    *,
    kinds: Sequence[str] | None = None,
    paths: Sequence[str] | None = None,
    min_score: float | None = None,
) -> list[CodeChunk]:
    """Find the nearest chunk vectors. Caller applies overlapping-span collapse."""
    clauses = ["repo_root = :repo_root"]
    params: dict[str, object] = {
        "repo_root": repo_root,
        "query": format_vector(query_vector),
        "top_k": top_k,
    }
    bind_expanding: list[str] = []
    kind_list = [item for item in (kinds or []) if item.strip()]
    path_list = [item.replace("\\", "/") for item in (paths or []) if item.strip()]
    if kind_list:
        clauses.append("kind IN :kinds")
        params["kinds"] = kind_list
        bind_expanding.append("kinds")
    if path_list:
        clauses.append("file_path IN :paths")
        params["paths"] = path_list
        bind_expanding.append("paths")
    if min_score is not None:
        clauses.append("1 - (embedding <=> CAST(:query AS vector)) >= :min_score")
        params["min_score"] = min_score

    sql = f"""
    SELECT symbol_id, file_path, kind, chunk_text, content_hash, start_line, end_line,
           chunk_tokens, truncated,
           1 - (embedding <=> CAST(:query AS vector)) AS score
    FROM code_embeddings
    WHERE {" AND ".join(clauses)}
    ORDER BY embedding <=> CAST(:query AS vector)
    LIMIT :top_k
    """
    stmt = text(sql)
    for name in bind_expanding:
        stmt = stmt.bindparams(bindparam(name, expanding=True))
    result = await session.execute(stmt, params)
    return [_chunk_from_row(row) for row in result]
