"""Bulk write helpers for code_embeddings (no Postgres)."""

from __future__ import annotations

from repo_intel.models import CodeChunk
from repo_intel.vector.store import insert_embeddings, upsert_embeddings


def _chunk(symbol_id: str) -> CodeChunk:
    return CodeChunk(
        symbol_id=symbol_id,
        file_path="a.py",
        kind="function",
        chunk_text="def x():\n    return 1\n",
        content_hash="c" * 64,
        start_line=1,
        end_line=2,
        chunk_tokens=1,
    )


class _RecordingSession:
    def __init__(self) -> None:
        self.calls: list[object] = []

    async def execute(self, stmt: object, params: object = None) -> None:
        self.calls.append(params)


async def test_insert_embeddings_sends_one_batch_not_one_row() -> None:
    session = _RecordingSession()
    rows = [(_chunk(f"a.py::f{i}"), [0.1, 0.2]) for i in range(3)]
    await insert_embeddings(session, "/repo", rows)
    assert len(session.calls) == 1
    batch = session.calls[0]
    assert isinstance(batch, list)
    assert len(batch) == 3


async def test_upsert_embeddings_skips_empty() -> None:
    session = _RecordingSession()
    await upsert_embeddings(session, "/repo", [])
    assert session.calls == []
