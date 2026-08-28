"""Index + query methods against Postgres (working-tree source of truth)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from repo_intel.exceptions import FileNotIndexedError, StaleIndexError, SymbolNotFoundError
from repo_intel.indexers.treesitter import (
    get_file_structure,
    get_indexed_parse_status,
    get_symbol_body,
    get_symbol_signature,
    index_repo,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "source_tree"


async def test_index_repo_parses_fixture_and_skips_syntax_errors(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    tree = _copy_fixture(tmp_path)
    stats = await index_repo(tree, db_session)

    assert stats.files_seen >= 6
    assert stats.files_parse_error == 1
    assert stats.files_parsed_ok == stats.files_seen - stats.files_parse_error
    assert stats.per_extension[".py"].parse_error == 1
    assert stats.per_extension[".py"].parsed_ok >= 3
    assert stats.per_extension[".ts"].parsed_ok == 1
    assert stats.per_extension[".tsx"].parsed_ok == 1
    assert stats.symbols_indexed > 0
    assert await get_indexed_parse_status(db_session, tree, "src/broken.py") == "parse_error"
    assert await get_indexed_parse_status(db_session, tree, "ignored/secret.py") is None


async def test_file_structure_signature_and_body_match_working_tree(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    tree = _copy_fixture(tmp_path)
    await index_repo(tree, db_session)

    structure = await get_file_structure(db_session, tree, "src/auth.py")
    kinds = {symbol.kind for symbol in structure}
    names = {symbol.name for symbol in structure}
    assert "class" in kinds
    assert "function" in kinds
    assert "method" in kinds
    assert "UserService" in names
    assert "validate_token" in names
    assert all(symbol.kind != "import" for symbol in structure)

    signature = await get_symbol_signature(
        db_session, tree, "src/auth.py::validate_token"
    )
    assert "def validate_token" in signature

    body = await get_symbol_body(db_session, tree, "src/auth.py::validate_token")
    on_disk = (tree / "src" / "auth.py").read_text(encoding="utf-8")
    validate = next(symbol for symbol in structure if symbol.id == "src/auth.py::validate_token")
    expected = "".join(
        on_disk.splitlines(keepends=True)[validate.start_line - 1 : validate.end_line]
    )
    assert body == expected
    assert "token.strip()" in body


async def test_uncommitted_style_file_is_indexed(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    tree = _copy_fixture(tmp_path)
    await index_repo(tree, db_session)
    structure = await get_file_structure(db_session, tree, "src/uncommitted.py")
    assert any(symbol.id == "src/uncommitted.py::working_tree_marker" for symbol in structure)


async def test_get_symbol_body_raises_stale_after_disk_edit(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    tree = _copy_fixture(tmp_path)
    await index_repo(tree, db_session)
    target = tree / "src" / "auth.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    with pytest.raises(StaleIndexError) as exc:
        await get_symbol_body(db_session, tree, "src/auth.py::validate_token")
    assert "src/auth.py" in exc.value.stale_paths


async def test_full_reindex_picks_up_working_tree_edit(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    tree = _copy_fixture(tmp_path)
    await index_repo(tree, db_session)
    marker = tree / "src" / "uncommitted.py"
    marker.write_text(
        'def working_tree_marker() -> str:\n    return "after-edit"\n',
        encoding="utf-8",
    )
    await index_repo(tree, db_session)
    body = await get_symbol_body(db_session, tree, "src/uncommitted.py::working_tree_marker")
    assert "after-edit" in body


async def test_unknown_symbol_and_file_fail_closed(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    tree = _copy_fixture(tmp_path)
    await index_repo(tree, db_session)
    with pytest.raises(SymbolNotFoundError):
        await get_symbol_signature(db_session, tree, "src/auth.py::does_not_exist")
    with pytest.raises(FileNotIndexedError):
        await get_file_structure(db_session, tree, "ignored/secret.py")


def _copy_fixture(tmp_path: Path) -> Path:
    """Copy so tests can edit files without mutating the committed fixture."""
    dest = tmp_path / "tree"
    shutil.copytree(FIXTURE, dest)
    return dest
