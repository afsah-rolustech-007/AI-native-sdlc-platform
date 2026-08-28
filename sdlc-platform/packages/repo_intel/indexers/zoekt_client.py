"""Zoekt lexical/trigram search over the local working tree (Phase 03 Section 02).

Lifecycle (MVP — revisited as an operated service in Phase 11):
- Index: one-shot `zoekt-index` into a per-repo shard directory (not ~/.zoekt unless
  the caller chooses that path).
- Search: one-shot `zoekt -jsonl` against those shards. `zoekt-webserver` is optional
  (`make zoekt-webserver`) for a human UI; `ZoektClient.search` does not talk to it.
- Full shard rebuild on every `build_index` is the Section 02/05 compromise. Section 05
  may keep that for Zoekt while scoping Tree-sitter/pgvector. Do not auto-reindex on
  search.

Source of truth is the working tree. We do **not** point Zoekt at a git checkout.
Zoekt's own walker only skips `.git/.hg/.svn`, which is not the catalog deny list, so
we stage a mirror of `walk_working_tree()` files and index that mirror. Same file set
as Tree-sitter. Same bytes as the SHA-256 catalog (copied from `FileSnapshot.content`).

This client does not read Postgres. Whole-tree `StaleIndexError` is Section 05/06.
A missing index raises `ZoektNotIndexedError` (fail-closed), never an empty hit list.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from common.config import get_settings
from repo_intel.exceptions import ZoektIndexError, ZoektNotIndexedError, ZoektSearchError
from repo_intel.indexers.catalog import FileSnapshot, resolve_repo_root, walk_working_tree
from repo_intel.indexers.zoekt_parse import parse_search_output, rank_and_clip
from repo_intel.indexers.zoekt_runner import ZoektCommandRunner, detect_zoekt_runner
from repo_intel.models import SearchHit

logger = logging.getLogger("sdlc.repo_intel")

BUILD_MARKER = "zoekt_build.json"
DEFAULT_TIMEOUT_S = 120.0


@dataclass(frozen=True)
class ZoektIndexStats:
    repo_root: str
    index_dir: str
    files_indexed: int
    runner: str


def write_eligible_tree(repo_root: Path | str, dest: Path) -> list[FileSnapshot]:
    """Copy catalog-eligible files into `dest`, preserving relative paths.

    Uses `FileSnapshot.content` so Zoekt hashes the same bytes Section 01 cataloged.
    """
    snapshots = walk_working_tree(repo_root)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for snapshot in snapshots:
        target = dest / snapshot.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(snapshot.content)
    return snapshots


def resolve_zoekt_index_dir(index_dir: Path | str | None, repo_root: Path) -> Path:
    """Shard directory. Default is out-of-tree so the catalog walk never sees shards."""
    if index_dir is not None and str(index_dir).strip():
        return Path(index_dir).expanduser().resolve()
    configured = get_settings().ri_zoekt_index_dir.strip()
    if configured:
        return Path(configured).expanduser().resolve()
    digest = hashlib.sha256(str(repo_root.resolve()).encode("utf-8")).hexdigest()[:16]
    return Path.home() / ".cache" / "sdlc-platform" / "zoekt" / digest


def is_zoekt_indexed(index_dir: Path) -> bool:
    marker = index_dir / BUILD_MARKER
    return marker.is_file()


class ZoektClient:
    """Build and query a Zoekt index for one working-tree `repo_root`."""

    def __init__(
        self,
        repo_root: Path | str | None = None,
        index_dir: Path | str | None = None,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        runner: ZoektCommandRunner | None = None,
    ) -> None:
        self.repo_root = resolve_repo_root(repo_root)
        self.index_dir = resolve_zoekt_index_dir(index_dir, self.repo_root)
        self.timeout_s = timeout_s
        self._runner = runner

    def _runner_or_detect(self) -> ZoektCommandRunner:
        if self._runner is None:
            self._runner = detect_zoekt_runner()
        return self._runner

    def build_index(self, root_path: Path | str | None = None) -> ZoektIndexStats:
        """Full Zoekt rebuild from the current working tree. Safe to call after disk edits.

        `root_path` must match this client's `repo_root` when provided. Indexing a
        different tree into these shards would silently mix corpora.
        """
        root = resolve_repo_root(root_path) if root_path is not None else self.repo_root
        if root != self.repo_root:
            raise ValueError(
                f"build_index root_path {root} does not match ZoektClient repo_root "
                f"{self.repo_root}"
            )
        runner = self._runner_or_detect()
        self.index_dir.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix="sdlc-zoekt-src-"))
        shards = Path(tempfile.mkdtemp(prefix="sdlc-zoekt-idx-"))
        swapped = False
        try:
            snapshots = write_eligible_tree(root, staging)
            result = runner.run_index(staging, shards, self.timeout_s)
            if result.timed_out:
                raise ZoektIndexError(
                    f"zoekt-index timed out after {self.timeout_s}s for {root}"
                )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip() or "zoekt-index failed"
                raise ZoektIndexError(detail)
            _write_marker(shards, file_count=len(snapshots))
            _swap_directory(shards, self.index_dir)
            swapped = True
            logger.info(
                "zoekt index built",
                extra={
                    "repo_root": str(root),
                    "index_dir": str(self.index_dir),
                    "files_indexed": len(snapshots),
                    "runner": runner.mode,
                },
            )
            return ZoektIndexStats(
                repo_root=str(root),
                index_dir=str(self.index_dir),
                files_indexed=len(snapshots),
                runner=runner.mode,
            )
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            if not swapped:
                shutil.rmtree(shards, ignore_errors=True)

    def search(self, query: str, top_k: int) -> list[SearchHit]:
        """Lexical search. Does not reindex. Missing index fails closed."""
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("search query must be a non-empty string")
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        if not is_zoekt_indexed(self.index_dir):
            raise ZoektNotIndexedError(str(self.index_dir))
        runner = self._runner_or_detect()
        result = runner.run_search(self.index_dir, cleaned, self.timeout_s)
        if result.timed_out:
            raise ZoektSearchError(f"zoekt search timed out after {self.timeout_s}s")
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip() or "zoekt search failed"
            raise ZoektSearchError(detail)
        hits = parse_search_output(result.stdout, jsonl=True)
        return rank_and_clip(hits, top_k)

    def search_codebase(self, query: str, top_k: int) -> list[SearchHit]:
        """Alias used by the later RepositoryIntelligence fusion layer."""
        return self.search(query, top_k)


def search_codebase(
    query: str,
    top_k: int,
    *,
    repo_root: Path | str | None = None,
    index_dir: Path | str | None = None,
) -> list[SearchHit]:
    """Module-level `search_codebase(query, top_k)` for Section 06 to wrap."""
    return ZoektClient(repo_root, index_dir).search(query, top_k)


def _write_marker(index_dir: Path, *, file_count: int) -> None:
    (index_dir / BUILD_MARKER).write_text(
        f'{{"version": 1, "file_count": {file_count}}}\n',
        encoding="utf-8",
    )


def _swap_directory(src: Path, dest: Path) -> None:
    """Replace dest with src. On failure, restore dest when a backup exists.

    Uses `shutil.move` so a /tmp staging dir can land in ~/.cache (cross-device).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    backup = dest.parent / f".{dest.name}.bak"
    if backup.exists():
        shutil.rmtree(backup)
    if dest.exists():
        dest.rename(backup)
    try:
        shutil.move(str(src), str(dest))
    except OSError:
        if backup.exists() and not dest.exists():
            backup.rename(dest)
        raise
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
