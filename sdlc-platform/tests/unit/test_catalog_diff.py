"""Section 05: the working-tree vs catalog diff is a pure function — test it directly."""

from __future__ import annotations

from repo_intel.indexers.catalog import FileSnapshot, diff_snapshots


def _snap(path: str, digest: str) -> FileSnapshot:
    return FileSnapshot(
        relative_path=path,
        content_hash=digest,
        size_bytes=1,
        mtime_ns=0,
        language="python",
        content=b"x",
    )


def test_unchanged_files_are_counted_not_reparsed() -> None:
    diff = diff_snapshots([_snap("a.py", "h1"), _snap("b.py", "h2")], {"a.py": "h1", "b.py": "h2"})

    assert diff.is_empty
    assert diff.unchanged == 2
    assert diff.changed_paths == []


def test_created_modified_and_deleted_are_separated() -> None:
    diff = diff_snapshots(
        [_snap("a.py", "h1"), _snap("b.py", "NEW"), _snap("c.py", "h3")],
        {"a.py": "h1", "b.py": "h2", "gone.py": "h4"},
    )

    assert diff.created == ["c.py"]
    assert diff.modified == ["b.py"]
    assert diff.deleted == ["gone.py"]
    assert diff.unchanged == 1
    assert diff.changed_paths == ["b.py", "c.py"]


def test_mtime_does_not_matter_only_content_hash() -> None:
    touched = FileSnapshot("a.py", "h1", size_bytes=1, mtime_ns=999, language="python", content=b"x")

    assert diff_snapshots([touched], {"a.py": "h1"}).is_empty


def test_rename_is_reported_as_delete_plus_create() -> None:
    diff = diff_snapshots([_snap("new.py", "h1")], {"old.py": "h1"})

    assert diff.created == ["new.py"]
    assert diff.deleted == ["old.py"]


def test_scope_limits_deletes_to_the_requested_paths() -> None:
    """reindex_paths(['a.py']) must not claim every other cataloged file was deleted."""
    diff = diff_snapshots([], {"a.py": "h1", "untouched.py": "h2"}, scope={"a.py"})

    assert diff.deleted == ["a.py"]
    assert "untouched.py" not in diff.deleted
