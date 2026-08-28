"""Working-tree discovery for Repository Intelligence.

Source of truth is files on disk under `repo_root`, including uncommitted edits.
`.gitignore` is used only as ignore-pattern syntax — this module never calls git.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import pathspec

from common.config import get_settings

# ~1 MiB. Larger files are excluded from the eligible set (not cataloged).
MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024

DENIED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
    }
)

# v1 languages. Additional suffixes are additive later; they are not walked yet.
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
}


@dataclass(frozen=True)
class FileSnapshot:
    """One eligible file as it existed when we read it. `content_hash` is of `content`."""

    relative_path: str
    content_hash: str
    size_bytes: int
    mtime_ns: int
    language: str
    content: bytes

    def __repr__(self) -> str:
        return (
            f"FileSnapshot({self.relative_path!r}, language={self.language!r}, "
            f"hash={self.content_hash[:12]}…)"
        )


def sha256_bytes(data: bytes) -> str:
    """Content identity used by the catalog. mtime/size are never used as authority."""
    return hashlib.sha256(data).hexdigest()


def compute_catalog_hash(path_and_digest: list[tuple[str, str]]) -> str:
    """Hash of sorted `(relative_path, content_hash)` pairs. Not a git commit SHA."""
    digest = hashlib.sha256()
    for relative_path, content_hash in sorted(path_and_digest, key=lambda item: item[0]):
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def language_for_path(path: Path) -> str | None:
    if path.name.endswith(".d.ts"):
        return None
    return SUPPORTED_EXTENSIONS.get(path.suffix.lower())


def resolve_repo_root(repo_root: Path | str | None = None) -> Path:
    """Absolute directory to index. Never inferred from `git rev-parse`."""
    if repo_root is not None and str(repo_root).strip():
        path = Path(repo_root).expanduser().resolve()
    else:
        configured = get_settings().ri_repo_root.strip()
        if not configured:
            raise ValueError(
                "repo_root is required: pass a filesystem path or set RI_REPO_ROOT. "
                "Do not infer it from git."
            )
        path = Path(configured).expanduser().resolve()
    if not path.is_dir():
        raise NotADirectoryError(f"repo_root is not a directory: {path}")
    return path


def posix_relative(repo_root: Path, path: Path) -> str:
    """Relative posix path used as catalog identity and Symbol.file_path.

    Paths are not lowercased: the working tree is case-sensitive on Linux.
    """
    return path.resolve().relative_to(repo_root).as_posix()


def _is_denied_directory(name: str) -> bool:
    return name in DENIED_DIRECTORY_NAMES or name.endswith(".egg-info")


def _load_gitignore(repo_root: Path) -> pathspec.PathSpec | None:
    """Root `.gitignore` only, as ignore-file format. Nested gitignore is deferred."""
    gitignore = repo_root / ".gitignore"
    if not gitignore.is_file():
        return None
    try:
        lines = gitignore.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise OSError(f"could not read {gitignore}: {exc}") from exc
    return pathspec.GitIgnoreSpec.from_lines(lines)


def _is_ignored(spec: pathspec.PathSpec | None, relative_posix: str, is_dir: bool) -> bool:
    if spec is None:
        return False
    if spec.match_file(relative_posix):
        return True
    return bool(is_dir and spec.match_file(relative_posix.rstrip("/") + "/"))


def walk_working_tree(repo_root: Path | str) -> list[FileSnapshot]:
    """Read every eligible source file under `repo_root` and SHA-256 its bytes.

    Untracked files that are not ignored are included. Git is not consulted.
    """
    root = resolve_repo_root(repo_root)
    ignore_spec = _load_gitignore(root)
    snapshots: list[FileSnapshot] = []

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        kept_dirs: list[str] = []
        for name in dirnames:
            if _is_denied_directory(name):
                continue
            child = current / name
            if child.is_symlink():
                continue
            rel_dir = posix_relative(root, child)
            if _is_ignored(ignore_spec, rel_dir, is_dir=True):
                continue
            kept_dirs.append(name)
        dirnames[:] = sorted(kept_dirs)

        for name in filenames:
            path = current / name
            if path.is_symlink():
                continue
            language = language_for_path(path)
            if language is None:
                continue
            relative_path = posix_relative(root, path)
            if _is_ignored(ignore_spec, relative_path, is_dir=False):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_size > MAX_FILE_SIZE_BYTES:
                continue
            try:
                content = path.read_bytes()
            except OSError:
                continue
            if len(content) > MAX_FILE_SIZE_BYTES:
                continue
            snapshots.append(
                FileSnapshot(
                    relative_path=relative_path,
                    content_hash=sha256_bytes(content),
                    size_bytes=len(content),
                    mtime_ns=stat.st_mtime_ns,
                    language=language,
                    content=content,
                )
            )

    snapshots.sort(key=lambda item: item.relative_path)
    return snapshots
