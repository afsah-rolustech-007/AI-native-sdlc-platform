"""pgvector semantic index against the working-tree fixture (Phase 03 Section 04)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from tests.contract.fakes import FakeAdapter
from tests.helpers.hashing_adapter import HashingAdapter

from repo_intel.exceptions import (
    EmbeddingDimensionError,
    EmbeddingIndexError,
    EmbeddingsNotIndexedError,
)
from repo_intel.vector.pgvector_client import PgvectorClient
from repo_intel.vector.store import hashes_for_file

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "source_tree"
VALIDATE = "src/auth.py::validate_token"
FORMAT_CENTS = "src/models.ts::formatCents"
NL_VALIDATE = "function that validates user input"
NL_CURRENCY = "format currency as a dollar string"
SIMILAR_VALIDATE = '''
def check_access(token: str) -> bool:
    """Return True when the token has non-whitespace content."""
    return bool(token.strip())
'''


class _UnitVectorAdapter:
    """Avoid HashingAdapter on pathological long strings (n-gram loops)."""

    def __init__(self) -> None:
        self.embed_calls: list[list[str]] = []
        self._pricing = HashingAdapter().pricing

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls.append(list(texts))
        vector = [0.0] * 2048
        vector[0] = 1.0
        return [list(vector) for _ in texts]

    def complete(self, request: object) -> None:
        raise NotImplementedError

    def stream(self, request: object) -> None:
        raise NotImplementedError

    def call_tools(self, request: object, tools: object) -> None:
        raise NotImplementedError

    @property
    def pricing(self) -> object:
        return self._pricing

    @property
    def capability_score(self) -> int:
        return 0


def _copy_fixture(tmp_path: Path) -> Path:
    dest = tmp_path / "tree"
    shutil.copytree(FIXTURE, dest)
    return dest


async def test_search_before_index_fails_closed(db_session: AsyncSession, tmp_path: Path) -> None:
    tree = _copy_fixture(tmp_path)
    client = PgvectorClient(db_session, HashingAdapter(), tree)
    with pytest.raises(EmbeddingsNotIndexedError):
        await client.search_concepts(NL_VALIDATE, 5)


async def test_empty_query_and_top_k_are_rejected(db_session: AsyncSession, tmp_path: Path) -> None:
    tree = _copy_fixture(tmp_path)
    client = PgvectorClient(db_session, HashingAdapter(), tree)
    with pytest.raises(ValueError):
        await client.search_concepts("   ", 5)
    with pytest.raises(ValueError):
        await client.search_concepts("token", 0)


async def test_wrong_embedding_width_fails_closed(db_session: AsyncSession, tmp_path: Path) -> None:
    tree = _copy_fixture(tmp_path)
    client = PgvectorClient(db_session, FakeAdapter(), tree)
    with pytest.raises(EmbeddingDimensionError) as exc:
        await client.index_working_tree()
    assert exc.value.got == 2
    assert exc.value.expected == 2048


async def test_adapter_failure_is_not_empty_hits(db_session: AsyncSession, tmp_path: Path) -> None:
    tree = _copy_fixture(tmp_path)
    client = PgvectorClient(db_session, FakeAdapter(fail_times=1), tree)
    with pytest.raises(EmbeddingIndexError):
        await client.index_working_tree()


async def test_index_embeds_symbol_chunks_not_ignored_or_broken(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    tree = _copy_fixture(tmp_path)
    client = PgvectorClient(db_session, HashingAdapter(), tree)
    stats = await client.index_working_tree()
    assert stats.files_seen >= 6
    assert stats.chunks_embedded == 12
    assert stats.chunks_skipped_unchanged == 0

    ids = {
        row[0]
        for row in (
            await db_session.execute(
                text("SELECT symbol_id FROM code_embeddings WHERE repo_root = :root"),
                {"root": str(tree.resolve())},
            )
        )
    }
    assert VALIDATE in ids
    assert FORMAT_CENTS in ids
    assert "src/uncommitted.py::working_tree_marker" in ids
    assert all("broken.py" not in symbol_id for symbol_id in ids)
    assert all("secret.py" not in symbol_id for symbol_id in ids)
    assert all("::module:" not in symbol_id for symbol_id in ids)
    assert all("::import:" not in symbol_id for symbol_id in ids)

    col = await db_session.execute(
        text(
            "SELECT format_type(a.atttypid, a.atttypmod) "
            "FROM pg_attribute a "
            "JOIN pg_class c ON a.attrelid = c.oid "
            "WHERE c.relname = 'code_embeddings' AND a.attname = 'embedding'"
        )
    )
    assert col.scalar_one() == "vector(2048)"


async def test_search_concepts_ranks_validate_token(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    tree = _copy_fixture(tmp_path)
    client = PgvectorClient(db_session, HashingAdapter(), tree)
    await client.index_working_tree()
    hits = await client.search_concepts(NL_VALIDATE, 12)
    ids = [hit.symbol_id for hit in hits]
    assert VALIDATE in ids[:3]
    scores = {hit.symbol_id: hit.score for hit in hits}
    assert scores[VALIDATE] is not None
    assert scores[FORMAT_CENTS] is not None
    assert scores[VALIDATE] > scores[FORMAT_CENTS]
    assert all(hit.kind for hit in hits)
    assert all(hit.chunk_tokens > 0 for hit in hits)
    _assert_no_overlapping_spans(hits)
    currency = await client.search_concepts(NL_CURRENCY, 5)
    assert FORMAT_CENTS in [hit.symbol_id for hit in currency]


async def test_find_similar_implementations_finds_validate_token(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    tree = _copy_fixture(tmp_path)
    client = PgvectorClient(db_session, HashingAdapter(), tree)
    await client.index_working_tree()
    hits = await client.find_similar_implementations(SIMILAR_VALIDATE, 3)
    assert hits[0].symbol_id == VALIDATE


async def test_changing_unrelated_file_does_not_rewrite_auth_rows(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    tree = _copy_fixture(tmp_path)
    adapter = HashingAdapter()
    client = PgvectorClient(db_session, adapter, tree)
    await client.index_working_tree()
    root = str(tree.resolve())
    before = await hashes_for_file(db_session, root, "src/auth.py")
    assert VALIDATE in before
    adapter.embed_calls.clear()

    (tree / "src" / "uncommitted.py").write_text(
        'def working_tree_marker() -> str:\n    return "after-edit"\n',
        encoding="utf-8",
    )
    stats = await client.reembed_paths(["src/uncommitted.py"])
    assert stats.files_seen == 1
    assert stats.chunks_embedded == 1
    assert stats.chunks_skipped_unchanged == 0
    after = await hashes_for_file(db_session, root, "src/auth.py")
    assert after == before
    embedded = [text for batch in adapter.embed_calls for text in batch]
    assert embedded
    assert all("validate_token" not in item for item in embedded)


async def test_reembed_paths_skips_unchanged_chunk_hash(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    tree = _copy_fixture(tmp_path)
    adapter = HashingAdapter()
    client = PgvectorClient(db_session, adapter, tree)
    await client.index_working_tree()
    adapter.embed_calls.clear()
    stats = await client.reembed_paths(["src/auth.py"])
    assert stats.chunks_embedded == 0
    assert stats.chunks_skipped_unchanged == 4
    assert adapter.embed_calls == []


async def test_delete_path_removes_only_that_file(db_session: AsyncSession, tmp_path: Path) -> None:
    tree = _copy_fixture(tmp_path)
    client = PgvectorClient(db_session, HashingAdapter(), tree)
    await client.index_working_tree()
    await client.delete_path("src/auth.py")
    hits = await client.search_concepts(NL_VALIDATE, 5)
    assert VALIDATE not in [hit.symbol_id for hit in hits]
    remaining = await hashes_for_file(db_session, str(tree.resolve()), "src/payments.py")
    assert remaining


async def test_index_working_tree_skips_unchanged_hashes(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    tree = _copy_fixture(tmp_path)
    adapter = HashingAdapter()
    client = PgvectorClient(db_session, adapter, tree)
    first = await client.index_working_tree()
    assert first.chunks_embedded == 12
    adapter.embed_calls.clear()
    second = await client.index_working_tree()
    assert second.chunks_embedded == 0
    assert second.chunks_skipped_unchanged == 12
    assert adapter.embed_calls == []


async def test_reembed_paths_does_not_walk_the_whole_tree(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = _copy_fixture(tmp_path)
    client = PgvectorClient(db_session, HashingAdapter(), tree)
    await client.index_working_tree()

    def _must_not_walk(*_args: object, **_kwargs: object) -> list:
        raise AssertionError("reembed_paths must use read_paths, not walk_working_tree")

    monkeypatch.setattr("repo_intel.vector.pgvector_client.walk_working_tree", _must_not_walk)
    stats = await client.reembed_paths(["src/auth.py"])
    assert stats.files_seen == 1
    assert stats.chunks_embedded == 0
    assert stats.chunks_skipped_unchanged == 4


async def test_search_filters_kinds_paths_and_min_score(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    tree = _copy_fixture(tmp_path)
    client = PgvectorClient(db_session, HashingAdapter(), tree)
    await client.index_working_tree()
    functions = await client.search_concepts(NL_VALIDATE, 12, kinds=["function"])
    assert functions
    assert all(hit.kind == "function" for hit in functions)
    assert VALIDATE in [hit.symbol_id for hit in functions]
    scoped = await client.search_concepts(NL_VALIDATE, 12, paths=["src/auth.py"])
    assert scoped
    assert all(hit.file_path == "src/auth.py" for hit in scoped)
    with pytest.raises(ValueError):
        await client.search_concepts(NL_VALIDATE, 5, min_score=1.1)
    floor = await client.search_concepts(NL_VALIDATE, 12, min_score=1.0)
    assert VALIDATE not in [hit.symbol_id for hit in floor]


async def test_reembed_paths_move_keeps_one_row(db_session: AsyncSession, tmp_path: Path) -> None:
    tree = tmp_path / "move"
    (tree / "src").mkdir(parents=True)
    (tree / "src" / "origin.py").write_text(
        "def relocated() -> int:\n    return 7\n", encoding="utf-8"
    )
    client = PgvectorClient(db_session, HashingAdapter(), tree)
    await client.index_working_tree()
    (tree / "src" / "origin.py").write_text("# gone\n", encoding="utf-8")
    (tree / "src" / "dest.py").write_text(
        "def relocated() -> int:\n    return 7\n", encoding="utf-8"
    )
    await client.reembed_paths(["src/origin.py", "src/dest.py"])
    ids = {
        row[0]
        for row in (
            await db_session.execute(
                text("SELECT symbol_id FROM code_embeddings WHERE repo_root = :root"),
                {"root": str(tree.resolve())},
            )
        )
    }
    assert ids == {"src/dest.py::relocated"}


async def test_oversized_chunk_is_truncated_before_embed(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cap = 80
    monkeypatch.setattr("repo_intel.vector.chunks.MAX_CHUNK_CHARS", cap)
    tree = tmp_path / "huge"
    (tree / "src").mkdir(parents=True)
    lines = "\n".join(f"    n{i} = {i}" for i in range(30))
    (tree / "src" / "huge.py").write_text(
        f'def huge() -> None:\n    """big symbol"""\n{lines}\n',
        encoding="utf-8",
    )
    adapter = _UnitVectorAdapter()
    client = PgvectorClient(db_session, adapter, tree)
    stats = await client.index_working_tree()
    assert stats.chunks_embedded == 1
    embedded = [text for batch in adapter.embed_calls for text in batch]
    assert embedded
    assert all(len(item) <= cap for item in embedded)
    row = (
        await db_session.execute(
            text(
                "SELECT truncated, length(chunk_text) FROM code_embeddings WHERE repo_root = :root"
            ),
            {"root": str(tree.resolve())},
        )
    ).one()
    assert bool(row[0]) is True
    assert int(row[1]) <= cap


async def test_rebuild_write_failure_rolls_back_previous_rows(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = _copy_fixture(tmp_path)
    client = PgvectorClient(db_session, HashingAdapter(), tree)
    await client.index_working_tree()
    root = str(tree.resolve())
    before = int(
        (
            await db_session.execute(
                text("SELECT COUNT(*) FROM code_embeddings WHERE repo_root = :root"),
                {"root": root},
            )
        ).scalar_one()
    )
    assert before == 12

    async def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("insert failed")

    monkeypatch.setattr("repo_intel.vector.pgvector_client.insert_embeddings", _boom)
    with pytest.raises(EmbeddingIndexError):
        await client.index_working_tree(rebuild=True)
    after = int(
        (
            await db_session.execute(
                text("SELECT COUNT(*) FROM code_embeddings WHERE repo_root = :root"),
                {"root": root},
            )
        ).scalar_one()
    )
    assert after == before


def _assert_no_overlapping_spans(hits: list) -> None:
    """No two non-class hits from one file may cover the same lines.

    Class rows are exempt: their vector is signature + docstring only, so a class
    header and one of its methods are complementary results, not duplicates.
    """
    by_file: dict[str, list] = {}
    for hit in hits:
        if hit.kind == "class":
            continue
        by_file.setdefault(hit.file_path, []).append(hit)
    for items in by_file.values():
        for index, left in enumerate(items):
            for right in items[index + 1 :]:
                overlap = left.start_line <= right.end_line and right.start_line <= left.end_line
                assert not overlap, (left.symbol_id, right.symbol_id)


@pytest.mark.live
async def test_live_glm_search_concepts_if_embeddings_exist(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Optional: real GLMAdapter.embed(). Skipped without a key or embeddings route."""
    from common.config import get_settings
    from model_adapters.glm.adapter import GLMAdapter
    from repo_intel.vector.constants import EMBEDDING_DIMENSIONS

    get_settings.cache_clear()
    if not get_settings().glm_api_key:
        pytest.skip("GLM_API_KEY is not set")
    tree = _copy_fixture(tmp_path)
    adapter = GLMAdapter()
    try:
        probe = adapter.embed(["token validation"])
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Z.AI embeddings endpoint not available: {exc}")
    if not probe or len(probe[0]) != EMBEDDING_DIMENSIONS:
        pytest.skip(
            f"live embedding width is {0 if not probe else len(probe[0])}, "
            f"column expects {EMBEDDING_DIMENSIONS}"
        )
    client = PgvectorClient(db_session, adapter, tree)
    await client.index_working_tree()
    hits = await client.search_concepts(NL_VALIDATE, 5)
    assert VALIDATE in [hit.symbol_id for hit in hits]
