"""Zoekt lexical/trigram search over the local working tree (Phase 03 Section 02).

Big picture (no magic — just file copy + external CLI):
  1. Our Python code walks the repo and picks allowed files (same rules as Section 01).
  2. We copy those files into a temporary folder (the "mirror").
  3. We run the `zoekt-index` program on that mirror folder (a separate process).
  4. Zoekt writes search data ("shards") into another folder.
  5. Later, `search()` runs the `zoekt` program against those shards.

We never point Zoekt at the raw repo because Zoekt would index README, gitignored
files, etc. The mirror is how we control exactly what Zoekt sees.

Git is not involved. Postgres is not involved in Zoekt indexing/search here.
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

# Written into index_dir after a successful build. search() checks for this file
# so "never indexed" is an error, not confused with "query had zero matches".
BUILD_MARKER = "zoekt_build.json"
DEFAULT_TIMEOUT_S = 120.0


@dataclass(frozen=True)
class ZoektIndexStats:
    """Summary returned after build_index() finishes."""

    repo_root: str
    index_dir: str
    files_indexed: int
    runner: str  # "host" or "docker" — how we invoked zoekt-index


def write_eligible_tree(repo_root: Path | str, dest: Path) -> list[FileSnapshot]:
    """Build the temporary mirror that Zoekt will index.

    This is the core of "who creates the mirror": this function, called from
    build_index().

    Steps:
      walk_working_tree(repo_root)  → read each allowed file from disk into memory
      for each file: write bytes to dest/<same relative path>

    Example:
      repo:  /home/you/myproject/src/auth.py
      mirror: /tmp/sdlc-zoekt-src-abc123/src/auth.py   (same content, copied by us)
    """
    # Section 01 catalog walk: returns a list of FileSnapshot (path + file bytes + hash).
    snapshots = walk_working_tree(repo_root)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for snapshot in snapshots:
        # Keep the same folder layout inside the mirror (src/auth.py stays src/auth.py).
        target = dest / snapshot.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        # snapshot.content is the file bytes we already read during the walk.
        target.write_bytes(snapshot.content)
    return snapshots


def resolve_zoekt_index_dir(index_dir: Path | str | None, repo_root: Path) -> Path:
    """Where Zoekt shard files live on disk (not inside your repo by default)."""
    if index_dir is not None and str(index_dir).strip():
        return Path(index_dir).expanduser().resolve()
    configured = get_settings().ri_zoekt_index_dir.strip()
    if configured:
        return Path(configured).expanduser().resolve()
    # One cache folder per repo path so two projects do not share one index.
    digest = hashlib.sha256(str(repo_root.resolve()).encode("utf-8")).hexdigest()[:16]
    return Path.home() / ".cache" / "sdlc-platform" / "zoekt" / digest


def is_zoekt_indexed(index_dir: Path) -> bool:
    """True only after a successful build_index() wrote the marker file."""
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
        # Absolute path to the project folder on disk (from arg or RI_REPO_ROOT config).
        self.repo_root = resolve_repo_root(repo_root)
        # Where Zoekt shard files are stored (persistent between build and search).
        self.index_dir = resolve_zoekt_index_dir(index_dir, self.repo_root)
        self.timeout_s = timeout_s
        # Tests inject a fake runner; production uses host zoekt binaries or Docker.
        self._runner = runner

    def _runner_or_detect(self) -> ZoektCommandRunner:
        if self._runner is None:
            self._runner = detect_zoekt_runner()
        return self._runner

    def build_index(self, root_path: Path | str | None = None) -> ZoektIndexStats:
        """Full rebuild: mirror eligible files → zoekt-index → swap shards into index_dir.

        Flow (two temp dirs + one permanent index_dir):

          repo on disk
               │
               ▼
          write_eligible_tree()  ──►  staging/     (temp mirror of source files)
               │
               ▼
          zoekt-index staging → shards/   (temp Zoekt output)
               │
               ▼
          _swap_directory(shards → index_dir)   (replace old index atomically)
               │
               ▼
          delete staging temp dir

        If zoekt-index fails, we delete the temp shards and leave the old index_dir
        untouched so search() can still use the previous index.
        """
        root = resolve_repo_root(root_path) if root_path is not None else self.repo_root
        if root != self.repo_root:
            raise ValueError(
                f"build_index root_path {root} does not match ZoektClient repo_root "
                f"{self.repo_root}"
            )
        runner = self._runner_or_detect()
        self.index_dir.mkdir(parents=True, exist_ok=True)

        # Temp folder A: our mirror of source files (deleted in finally).
        staging = Path(tempfile.mkdtemp(prefix="sdlc-zoekt-src-"))
        # Temp folder B: where zoekt-index writes shards before we swap them in.
        shards = Path(tempfile.mkdtemp(prefix="sdlc-zoekt-idx-"))
        swapped = False
        try:
            # Step 1 — our code copies allowed files into staging/.
            snapshots = write_eligible_tree(root, staging)

            # Step 2 — subprocess: zoekt-index -index <shards> <staging>
            # (exact argv is built in zoekt_runner.py; we do not import Zoekt as a library.)
            result = runner.run_index(staging, shards, self.timeout_s)
            if result.timed_out:
                raise ZoektIndexError(f"zoekt-index timed out after {self.timeout_s}s for {root}")
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip() or "zoekt-index failed"
                raise ZoektIndexError(detail)

            # Step 3 — mark success, then move temp shards → permanent index_dir.
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
            # Always remove the source mirror. Remove failed shard temp dir only if swap
            # did not happen (successful swap moves shards into index_dir).
            shutil.rmtree(staging, ignore_errors=True)
            if not swapped:
                shutil.rmtree(shards, ignore_errors=True)

    def search(self, query: str, top_k: int) -> list[SearchHit]:
        """Run zoekt CLI against existing shards. Does not read your repo or reindex."""
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("search query must be a non-empty string")
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        if not is_zoekt_indexed(self.index_dir):
            raise ZoektNotIndexedError(str(self.index_dir))

        # Subprocess: zoekt -index_dir <index_dir> -jsonl <query>
        runner = self._runner_or_detect()
        result = runner.run_search(self.index_dir, cleaned, self.timeout_s)
        if result.timed_out:
            raise ZoektSearchError(f"zoekt search timed out after {self.timeout_s}s")
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip() or "zoekt search failed"
            raise ZoektSearchError(detail)

        # Turn Zoekt's JSON lines into our SearchHit objects, sort, take top_k.
        hits = parse_search_output(result.stdout, jsonl=True)
        return rank_and_clip(hits, top_k)

    def search_codebase(self, query: str, top_k: int) -> list[SearchHit]:
        """Same as search(); name matches the future RepositoryIntelligence API."""
        return self.search(query, top_k)


def search_codebase(
    query: str,
    top_k: int,
    *,
    repo_root: Path | str | None = None,
    index_dir: Path | str | None = None,
) -> list[SearchHit]:
    """Convenience wrapper: ZoektClient(...).search(...) without keeping a client."""
    return ZoektClient(repo_root, index_dir).search(query, top_k)


def _write_marker(index_dir: Path, *, file_count: int) -> None:
    """Small JSON file so is_zoekt_indexed() knows a build completed."""
    (index_dir / BUILD_MARKER).write_text(
        f'{{"version": 1, "file_count": {file_count}}}\n',
        encoding="utf-8",
    )


def _swap_directory(src: Path, dest: Path) -> None:
    """Atomically replace dest with src (rename old dest to .bak, then move src in).

    Why: if zoekt-index crashes halfway, we must not delete a working old index.
    Why shutil.move: temp dir may be on /tmp and index_dir on ~/.cache (different disks).
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
