"""Section 05 incremental indexing over a real Postgres + a real working tree."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from tests.helpers.hashing_adapter import HashingAdapter

from repo_intel.exceptions import RepoIntelError, StaleIndexError, SymbolNotFoundError
from repo_intel.indexers.incremental import IncrementalIndexer
from repo_intel.vector.pgvector_client import PgvectorClient

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "source_tree"
AUTH = "src/auth.py"
VALIDATE = "src/auth.py::validate_token"

pytestmark = pytest.mark.usefixtures("migrated_database_url")


def _tree(tmp_path: Path) -> Path:
    dest = tmp_path / "tree"
    shutil.copytree(FIXTURE, dest)
    return dest


def _indexer(session: AsyncSession, root: Path, adapter: HashingAdapter) -> IncrementalIndexer:
    # Zoekt binaries are optional on dev machines; Section 05 logic does not need them.
    return IncrementalIndexer(session, adapter, root, enable_zoekt=False)


async def _count(session: AsyncSession, table: str, root: Path) -> int:
    result = await session.execute(
        text(f"SELECT count(*) FROM {table} WHERE repo_root = :root"), {"root": str(root)}
    )
    return int(result.scalar_one())


async def test_first_index_populates_catalog_symbols_and_embeddings(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    indexer = _indexer(db_session, root, HashingAdapter())

    stats = await indexer.index()

    assert stats.created > 0
    assert stats.files_parsed == stats.created
    assert stats.symbols_indexed > 0
    assert stats.chunks_embedded > 0
    assert stats.catalog_hash
    assert await _count(db_session, "indexed_files", root) == stats.created
    assert await _count(db_session, "code_embeddings", root) == stats.chunks_embedded
    assert (await indexer.status()).state == "fresh"


async def test_reindex_with_no_edits_parses_and_embeds_nothing(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    adapter = HashingAdapter()
    indexer = _indexer(db_session, root, adapter)
    await indexer.index()
    adapter.embed_calls.clear()

    stats = await indexer.reindex()

    assert stats.files_parsed == 0
    assert stats.chunks_embedded == 0
    assert adapter.embed_calls == []
    assert stats.unchanged > 0


async def test_edit_reembeds_only_the_changed_symbol(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    adapter = HashingAdapter()
    indexer = _indexer(db_session, root, adapter)
    await indexer.index()
    before = await _count(db_session, "code_embeddings", root)
    adapter.embed_calls.clear()

    source = (root / AUTH).read_text(encoding="utf-8")
    (root / AUTH).write_text(
        source.replace(
            "return bool(token.strip())", "return bool(token.strip()) and len(token) > 2"
        ),
        encoding="utf-8",
    )

    stats = await indexer.reindex()

    assert stats.modified == 1
    assert stats.files_parsed == 1  # only the edited file was parsed
    assert stats.chunks_embedded == 1  # only validate_token's chunk changed
    assert stats.chunks_skipped_unchanged > 0  # UserService chunks were reused
    assert await _count(db_session, "code_embeddings", root) == before


async def test_delete_removes_catalog_symbols_and_vectors(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    indexer = _indexer(db_session, root, HashingAdapter())
    await indexer.index()

    (root / AUTH).unlink()
    stats = await indexer.reindex()

    assert stats.deleted == 1
    rows = await db_session.execute(
        text("SELECT count(*) FROM code_embeddings WHERE repo_root = :r AND file_path = :p"),
        {"r": str(root), "p": AUTH},
    )
    assert rows.scalar_one() == 0
    symbols = await db_session.execute(
        text("SELECT count(*) FROM symbols WHERE repo_root = :r AND file_path = :p"),
        {"r": str(root), "p": AUTH},
    )
    assert symbols.scalar_one() == 0


async def test_reindex_paths_only_touches_the_requested_files(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    adapter = HashingAdapter()
    indexer = _indexer(db_session, root, adapter)
    await indexer.index()

    # Two dirty files, but we only declare one of them.
    for path in (AUTH, "src/payments.py"):
        target = root / path
        target.write_text(target.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")

    stats = await indexer.reindex_paths([AUTH])

    assert stats.modified == 1
    assert stats.files_parsed == 1
    # The undeclared file is still dirty, so the tree is still stale — fail closed.
    status = await indexer.status()
    assert status.state == "stale"
    assert status.stale_paths == ["src/payments.py"]


async def test_move_keeps_one_row_when_both_paths_are_declared(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    indexer = _indexer(db_session, root, HashingAdapter())
    await indexer.index()

    moved = "src/auth_moved.py"
    (root / AUTH).rename(root / moved)
    await indexer.reindex_paths([AUTH, moved])

    paths = await db_session.execute(
        text("SELECT DISTINCT file_path FROM code_embeddings WHERE repo_root = :r"),
        {"r": str(root)},
    )
    live_paths = {row[0] for row in paths}
    assert AUTH not in live_paths  # old path's vectors are gone
    assert moved in live_paths  # new path has them exactly once
    assert (await indexer.status()).state == "fresh"


async def test_status_reports_unindexed_fresh_and_stale(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    indexer = _indexer(db_session, root, HashingAdapter())

    assert (await indexer.status()).state == "unindexed"
    await indexer.index()
    assert (await indexer.status()).state == "fresh"

    (root / AUTH).write_text("# gutted\n", encoding="utf-8")
    stale = await indexer.status()
    assert stale.state == "stale"
    assert stale.stale_paths == [AUTH]


async def test_assert_fresh_raises_stale_index_error(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    indexer = _indexer(db_session, root, HashingAdapter())
    await indexer.index()
    (root / AUTH).write_text("# gutted\n", encoding="utf-8")

    with pytest.raises(StaleIndexError) as excinfo:
        await indexer.assert_fresh()
    assert excinfo.value.stale_paths == [AUTH]


async def test_assert_fresh_on_never_indexed_tree_is_not_a_silent_pass(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    indexer = _indexer(db_session, _tree(tmp_path), HashingAdapter())

    with pytest.raises(StaleIndexError, match="never been indexed"):
        await indexer.assert_fresh()


async def test_embedding_failure_rolls_back_symbols_and_catalog(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A partial reindex must never be durable: no catalog row without its vectors."""
    root = _tree(tmp_path)
    indexer = _indexer(db_session, root, HashingAdapter())
    await indexer.index()
    before_files = await _count(db_session, "indexed_files", root)
    before_vectors = await _count(db_session, "code_embeddings", root)

    (root / AUTH).write_text("def brand_new(x):\n    return x\n", encoding="utf-8")

    def boom(self: PgvectorClient, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("provider is down")

    monkeypatch.setattr(PgvectorClient, "_embed_texts", boom)

    with pytest.raises(RepoIntelError):
        await indexer.reindex()

    assert await _count(db_session, "indexed_files", root) == before_files
    assert await _count(db_session, "code_embeddings", root) == before_vectors
    # Still stale, so Section 06 keeps refusing to read — no silent half-state.
    assert (await indexer.status()).state == "stale"


async def test_graph_is_patched_not_rebuilt_on_reindex(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    root = _tree(tmp_path)
    indexer = _indexer(db_session, root, HashingAdapter())
    await indexer.index()
    indexer.hydrate_graph()
    assert indexer.graph.get_callers(VALIDATE)

    (root / AUTH).write_text("def only_symbol():\n    return 1\n", encoding="utf-8")
    stats = await indexer.reindex()

    assert stats.graph_updated is True
    # The new symbol is live without a full rebuild.
    assert indexer.graph.get_callees("src/auth.py::only_symbol") == []
    # A dropped symbol nobody referenced is gone.
    with pytest.raises(SymbolNotFoundError):
        indexer.graph.get_callers("src/auth.py::UserService.ping")
    # But validate_token survives as a dangling call target: payments.py still
    # calls that name (Section 03 keeps referenced nodes so the caller file is
    # not re-parsed). That is a real unresolved reference, not stale data.
    assert {s.id for s in indexer.graph.get_callers(VALIDATE)} == {
        "src/payments.py::ChargeService.charge"
    }
