"""Catalog walk: working tree, ignore rules, SHA-256. No git."""

from __future__ import annotations

from pathlib import Path

from repo_intel.indexers.catalog import (
    MAX_FILE_SIZE_BYTES,
    read_paths,
    sha256_bytes,
    walk_working_tree,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "source_tree"


def test_walk_indexes_working_tree_files_without_git() -> None:
    snapshots = walk_working_tree(FIXTURE)
    paths = {item.relative_path for item in snapshots}
    assert "src/auth.py" in paths
    assert "src/uncommitted.py" in paths
    assert "src/models.ts" in paths
    assert "src/ui.tsx" in paths
    assert "src/broken.py" in paths
    assert "src/payments.py" in paths
    assert "ignored/secret.py" not in paths
    assert "README.md" not in paths
    assert not (FIXTURE / ".git").exists() 


def test_content_hash_is_sha256_of_file_bytes() -> None:
    snapshots = {item.relative_path: item for item in walk_working_tree(FIXTURE)}
    auth = snapshots["src/auth.py"]
    raw = (FIXTURE / "src" / "auth.py").read_bytes()
    assert auth.content_hash == sha256_bytes(raw)
    assert auth.size_bytes == len(raw)


def test_denied_directories_are_not_walked(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "hidden.py").write_text("def skip():\n    pass\n")
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.ts").write_text("export const x = 1;\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "auth.cpython-312.py").write_text("def cached():\n    pass\n")
    paths = {item.relative_path for item in walk_working_tree(tmp_path)}
    assert paths == {"src/ok.py"}


def test_gitignore_patterns_exclude_files_without_using_git(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("secret.py\nbuild/\n", encoding="utf-8")
    (tmp_path / "visible.py").write_text("def visible():\n    return 1\n")
    (tmp_path / "secret.py").write_text("def secret():\n    return 0\n")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.py").write_text("def built():\n    return 0\n")
    paths = {item.relative_path for item in walk_working_tree(tmp_path)}
    assert paths == {"visible.py"}


def test_files_over_size_cap_are_not_eligible(tmp_path: Path) -> None:
    (tmp_path / "small.py").write_text("def small():\n    return 1\n")
    (tmp_path / "huge.py").write_bytes(b"x" * (MAX_FILE_SIZE_BYTES + 1))
    paths = {item.relative_path for item in walk_working_tree(tmp_path)}
    assert paths == {"small.py"}


def test_symlinks_are_not_followed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("def outside():\n    return 1\n")
    (repo / "src").mkdir()
    (repo / "src" / "inside.py").write_text("def inside():\n    return 1\n")
    (repo / "src" / "link.py").symlink_to(outside)
    paths = {item.relative_path for item in walk_working_tree(repo)}
    assert paths == {"src/inside.py"}


def test_read_paths_reads_only_requested_eligible_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "src" / "other.py").write_text("def b():\n    return 2\n", encoding="utf-8")
    snapshots = read_paths(tmp_path, ["src/auth.py", "src/missing.py", "README.md"])
    assert [item.relative_path for item in snapshots] == ["src/auth.py"]


def test_read_paths_does_not_escape_repo_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "inside.py").write_text("def inside():\n    return 1\n")
    (tmp_path / "outside.py").write_text("def outside():\n    return 1\n")
    snapshots = read_paths(repo, ["../outside.py", "inside.py"])
    assert [item.relative_path for item in snapshots] == ["inside.py"]


def test_package_does_not_import_git() -> None:
    root = Path(__file__).resolve().parents[2] / "packages" / "repo_intel"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("import git", "from git")):
                offenders.append(f"{path.relative_to(root)}:{line_no}:{stripped}")
    assert offenders == []
