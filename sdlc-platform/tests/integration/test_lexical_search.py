"""Live Zoekt index + search against the working-tree fixture.

Skipped when neither host binaries nor the packaged Zoekt image are present.
These tests do not use git and do not talk to Postgres.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from repo_intel.indexers.zoekt_client import ZoektClient, search_codebase
from repo_intel.indexers.zoekt_runner import zoekt_is_available

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "source_tree"

pytestmark = [
    pytest.mark.zoekt,
    pytest.mark.skipif(
        not zoekt_is_available(),
        reason="Zoekt binaries or ghcr.io/sourcegraph/zoekt image required",
    ),
]


def _copy_fixture(tmp_path: Path) -> Path:
    dest = tmp_path / "tree"
    shutil.copytree(FIXTURE, dest)
    return dest


def test_known_answer_search_ranks_validate_token(tmp_path: Path) -> None:
    tree = _copy_fixture(tmp_path)
    client = ZoektClient(tree, tmp_path / "zoekt")
    stats = client.build_index(tree)
    assert stats.files_indexed >= 6
    hits = client.search("validate_token", 5)
    paths = [hit.file_path for hit in hits]
    assert "src/auth.py" in paths
    auth_hits = [hit for hit in hits if hit.file_path == "src/auth.py"]
    assert auth_hits
    assert any("validate_token" in hit.snippet for hit in auth_hits)
    assert auth_hits[0].line >= 1
    assert all(hit.file_path != "ignored/secret.py" for hit in hits)


def test_ignored_and_non_source_files_are_not_searchable(tmp_path: Path) -> None:
    tree = _copy_fixture(tmp_path)
    client = ZoektClient(tree, tmp_path / "zoekt")
    client.build_index()
    secret_hits = client.search("should_not_be_indexed", 10)
    assert secret_hits == []
    readme_hits = client.search("working-tree fixture", 10)
    assert readme_hits == []


def test_uncommitted_working_tree_string_is_searchable(tmp_path: Path) -> None:
    tree = _copy_fixture(tmp_path)
    client = ZoektClient(tree, tmp_path / "zoekt")
    client.build_index()
    hits = search_codebase(
        "indexed-without-git",
        5,
        repo_root=tree,
        index_dir=tmp_path / "zoekt",
    )
    assert any(hit.file_path == "src/uncommitted.py" for hit in hits)


def test_edit_on_disk_then_rebuild_finds_new_string(tmp_path: Path) -> None:
    tree = _copy_fixture(tmp_path)
    client = ZoektClient(tree, tmp_path / "zoekt")
    client.build_index()
    before = client.search("zoekt_rebuild_marker_alpha", 5)
    assert before == []

    target = tree / "src" / "auth.py"
    target.write_text(
        target.read_text(encoding="utf-8") + "\nMARKER = 'zoekt_rebuild_marker_alpha'\n",
        encoding="utf-8",
    )
    still_old = client.search("zoekt_rebuild_marker_alpha", 5)
    assert still_old == []

    client.build_index()
    after = client.search("zoekt_rebuild_marker_alpha", 5)
    assert any(hit.file_path == "src/auth.py" for hit in after)
    assert any("zoekt_rebuild_marker_alpha" in hit.snippet for hit in after)
