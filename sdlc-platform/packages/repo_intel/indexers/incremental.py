"""Working-tree incremental indexing (Phase 03 Section 05).

Keeps four stores aligned with bytes on disk under `repo_root`:
  catalog + symbols (Postgres) · pgvector · Zoekt shards · NetworkX (in memory)

How a reindex works:
  1. Walk eligible files, SHA-256 each one, diff against `indexed_files`.
  2. Parse every created/modified file ONCE; share that parse with symbols,
     graph edges, and embedding chunks.
  3. Embed only chunks whose chunk `content_hash` changed.
  4. Rebuild Zoekt (full rebuild is the documented MVP compromise) BEFORE the
     Postgres commit, so the catalog never claims a lexical index we do not have.
  5. Commit symbols + embeddings + catalog + snapshot in one transaction.
  6. Patch the in-memory graph last (it is rebuildable from disk).

Unchanged files are never re-parsed or re-embedded. A file is NOT reindexed just
because a file it imports changed — that expansion is `get_impact_set`, a query.

No filesystem watcher, no git hook, no git diff.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from tree_sitter import Tree

from model_adapters.base import ModelAdapter
from repo_intel.exceptions import (
    FileParseError,
    RepoIntelError,
    StaleIndexError,
    UnsupportedLanguageError,
    ZoektIndexError,
    ZoektUnavailableError,
)
from repo_intel.graph.networkx_client import NetworkXClient
from repo_intel.indexers.catalog import (
    FileSnapshot,
    compute_catalog_hash,
    diff_snapshots,
    read_paths,
    resolve_repo_root,
    walk_working_tree,
)
from repo_intel.indexers.treesitter import parse_source_and_tree
from repo_intel.indexers.zoekt_client import ZoektClient
from repo_intel.models import (
    CatalogDiff,
    CodeChunk,
    IndexStatus,
    ParseStatus,
    ReindexStats,
    Symbol,
)
from repo_intel.symbol_store import (
    delete_file_index,
    delete_repo_index,
    get_catalog_hash,
    list_catalog_hashes,
    replace_file_index,
    upsert_snapshot,
)
from repo_intel.vector.chunks import chunks_from_symbols
from repo_intel.vector.pgvector_client import PgvectorClient

logger = logging.getLogger("sdlc.repo_intel")


@dataclass
class _ParsedFile:
    """One Tree-sitter parse, reused by symbols, graph, and chunks."""

    snapshot: FileSnapshot
    symbols: list[Symbol]
    tree: Tree | None
    chunks: list[CodeChunk]
    parse_status: ParseStatus


def _parse_once(snapshot: FileSnapshot) -> _ParsedFile:
    """Parse a file a single time. A bad file is skipped, never fatal to the run."""
    try:
        source_text = snapshot.content.decode("utf-8")
    except UnicodeDecodeError:
        logger.warning("skipping %s: not valid UTF-8", snapshot.relative_path)
        return _ParsedFile(snapshot, [], None, [], "skipped")
    try:
        symbols, tree = parse_source_and_tree(
            snapshot.relative_path, snapshot.content, snapshot.language
        )
    except FileParseError as exc:
        logger.warning("skipping %s: %s", snapshot.relative_path, exc.detail)
        return _ParsedFile(snapshot, [], None, [], "parse_error")
    except UnsupportedLanguageError:
        logger.warning("skipping %s: no Tree-sitter grammar", snapshot.relative_path)
        return _ParsedFile(snapshot, [], None, [], "skipped")
    chunks = chunks_from_symbols(symbols, source_text)
    return _ParsedFile(snapshot, symbols, tree, chunks, "ok")


class IncrementalIndexer:
    """Owns `index` / `reindex` / `reindex_paths` / freshness for one `repo_root`.

    Section 06's RepositoryIntelligence is the only thing agents should call;
    this class is the machinery behind it.
    """

    def __init__(
        self,
        session: AsyncSession,
        adapter: ModelAdapter,
        repo_root: Path | str | None = None,
        *,
        vector: PgvectorClient | None = None,
        graph: NetworkXClient | None = None,
        zoekt: ZoektClient | None = None,
        enable_zoekt: bool = True,
    ) -> None:
        self.repo_root = resolve_repo_root(repo_root)
        self._session = session
        self.vector = vector or PgvectorClient(session, adapter, self.repo_root)
        self.graph = graph or NetworkXClient(self.repo_root)
        self._zoekt = zoekt
        self.enable_zoekt = enable_zoekt

    @property
    def zoekt(self) -> ZoektClient:
        if self._zoekt is None:
            self._zoekt = ZoektClient(self.repo_root)
        return self._zoekt

    async def status(self) -> IndexStatus:
        """Whole-tree freshness. Any stale eligible path makes the repo stale."""
        root = self.repo_root
        catalog = await list_catalog_hashes(self._session, root)
        if not catalog:
            return IndexStatus(repo_root=str(root), state="unindexed")
        snapshots = walk_working_tree(root)
        diff = diff_snapshots(snapshots, catalog)
        if diff.is_empty:
            return IndexStatus(
                repo_root=str(root),
                state="fresh",
                file_count=len(snapshots),
                catalog_hash=await get_catalog_hash(self._session, root),
            )
        stale = sorted({*diff.created, *diff.modified, *diff.deleted})
        return IndexStatus(
            repo_root=str(root),
            state="stale",
            file_count=len(snapshots),
            stale_paths=stale,
            catalog_hash=await get_catalog_hash(self._session, root),
        )

    async def assert_fresh(self) -> IndexStatus:
        """Fail closed before any read. Never serve a stale tree as current code."""
        state = await self.status()
        if state.state == "unindexed":
            raise StaleIndexError(
                [], f"{self.repo_root} has never been indexed; run index() first"
            )
        if state.state == "stale":
            raise StaleIndexError(state.stale_paths)
        return state

    async def index(self, *, rebuild: bool = False) -> ReindexStats:
        """First index, or a forced full rebuild that wipes this repo's rows."""
        if rebuild:
            logger.info("full rebuild requested for %s", self.repo_root)
            await delete_repo_index(self._session, self.repo_root)
            await self._session.commit()
            await self.vector.index_working_tree(rebuild=True)
        return await self.reindex()

    async def reindex(self) -> ReindexStats:
        """Hash-diff the whole tree, then update only what changed."""
        snapshots = walk_working_tree(self.repo_root)
        catalog = await list_catalog_hashes(self._session, self.repo_root)
        diff = diff_snapshots(snapshots, catalog)
        by_path = {snapshot.relative_path: snapshot for snapshot in snapshots}
        return await self._apply(diff, by_path, full_tree=True)

    async def reindex_paths(self, relative_paths: Sequence[str]) -> ReindexStats:
        """Scoped update after an agent (Phase 05+) wrote these paths.

        Pass both the old and new path of a move in one call. Paths outside the
        list are neither read nor re-embedded, and stay stale if they were edited.
        """
        wanted = {path.replace("\\", "/").strip() for path in relative_paths if path.strip()}
        if not wanted:
            return ReindexStats(repo_root=str(self.repo_root))
        snapshots = read_paths(self.repo_root, sorted(wanted))
        catalog = await list_catalog_hashes(self._session, self.repo_root)
        diff = diff_snapshots(snapshots, catalog, scope=wanted)
        by_path = {snapshot.relative_path: snapshot for snapshot in snapshots}
        return await self._apply(diff, by_path, full_tree=False)

    async def _apply(
        self,
        diff: CatalogDiff,
        by_path: dict[str, FileSnapshot],
        *,
        full_tree: bool,
    ) -> ReindexStats:
        started = time.perf_counter()
        root = self.repo_root
        stats = ReindexStats(
            repo_root=str(root),
            created=len(diff.created),
            modified=len(diff.modified),
            deleted=len(diff.deleted),
            unchanged=diff.unchanged,
        )
        if diff.is_empty:
            stats.catalog_hash = await self._refresh_snapshot(full_tree=full_tree)
            stats.elapsed_s = time.perf_counter() - started
            logger.info("reindex: no changes (%d unchanged)", diff.unchanged)
            return stats

        logger.info(
            "reindex: %d created, %d modified, %d deleted, %d unchanged",
            len(diff.created),
            len(diff.modified),
            len(diff.deleted),
            diff.unchanged,
        )

        # 1. Parse each changed file exactly once.
        parsed: list[_ParsedFile] = []
        for path in diff.changed_paths:
            snapshot = by_path.get(path)
            if snapshot is None:
                continue
            item = _parse_once(snapshot)
            parsed.append(item)
            stats.files_parsed += 1
            if item.parse_status == "parse_error":
                stats.files_parse_error += 1
            stats.symbols_indexed += len(item.symbols)

        # 2. Zoekt before the DB commit so the catalog never over-promises.
        stats.zoekt_rebuilt = self._rebuild_zoekt()

        # 3. One transaction: embeddings + symbols + catalog + snapshot.
        try:
            embed_stats = await self.vector.apply_chunks(
                {item.snapshot.relative_path: item.chunks for item in parsed},
                deleted_paths=diff.deleted,
                commit=False,
            )
            for path in diff.deleted:
                await delete_file_index(self._session, root, path)
            for item in parsed:
                await replace_file_index(
                    self._session, root, item.snapshot, item.symbols, item.parse_status
                )
            catalog_hash = await self._write_snapshot(full_tree=full_tree)
            await self._session.commit()
        except RepoIntelError:
            await self._session.rollback()
            raise
        except Exception as exc:
            await self._session.rollback()
            logger.error("reindex failed, rolled back: %s", exc)
            raise RepoIntelError(f"reindex failed for {root}: {exc}") from exc

        stats.chunks_embedded = embed_stats.chunks_embedded
        stats.chunks_skipped_unchanged = embed_stats.chunks_skipped_unchanged
        stats.catalog_hash = catalog_hash

        # 4. Graph last — in memory, rebuildable, never blocks durability.
        stats.graph_updated = self._patch_graph(parsed, diff.deleted)

        stats.elapsed_s = time.perf_counter() - started
        logger.info(
            "reindex done in %.2fs: %d parsed, %d embedded, %d chunks unchanged",
            stats.elapsed_s,
            stats.files_parsed,
            stats.chunks_embedded,
            stats.chunks_skipped_unchanged,
        )
        return stats

    def _rebuild_zoekt(self) -> bool:
        """Full Zoekt rebuild — the documented MVP compromise (spec §3).

        Only Zoekt full-rebuilds. Symbols, embeddings, and the graph stay scoped.
        Missing binaries are not fatal to indexing: lexical search itself still
        fails closed with ZoektNotIndexedError until a build succeeds.
        """
        if not self.enable_zoekt:
            return False
        try:
            result = self.zoekt.build_index()
        except ZoektUnavailableError as exc:
            logger.warning("zoekt not available, lexical index not updated: %s", exc)
            return False
        except ZoektIndexError as exc:
            logger.error("zoekt rebuild failed, previous shards kept: %s", exc)
            raise
        logger.info("zoekt rebuilt: %d files", result.files_indexed)
        return True

    def _patch_graph(self, parsed: list[_ParsedFile], deleted: Sequence[str]) -> bool:
        """Apply scoped graph edits. A cold graph is hydrated from disk instead."""
        if not self.graph.is_built:
            logger.debug("graph not built yet; skipping patch (hydrate on first query)")
            return False
        for path in deleted:
            self.graph.remove_file(path)
        for item in parsed:
            self.graph.replace_file_parsed(
                item.snapshot.relative_path,
                item.snapshot.content,
                item.snapshot.language,
                item.symbols,
                item.tree,
            )
        return True

    def hydrate_graph(self) -> None:
        """Build the in-memory graph if this process has not built it yet.

        NetworkX is RAM-only, so a restart loses it while Postgres/Zoekt stay fresh.
        Callers must have passed the freshness check first — we read disk here.
        """
        if self.graph.is_built:
            return
        stats = self.graph.build(self.repo_root)
        logger.info(
            "graph hydrated: %d files, %d symbols, %d import edges",
            stats.file_nodes,
            stats.symbol_nodes,
            stats.import_edges,
        )

    async def _write_snapshot(self, *, full_tree: bool) -> str:
        """Recompute the repo-level catalog hash from the committed catalog rows."""
        pairs = list((await list_catalog_hashes(self._session, self.repo_root)).items())
        catalog_hash = compute_catalog_hash(pairs)
        await upsert_snapshot(
            self._session, self.repo_root, file_count=len(pairs), catalog_hash=catalog_hash
        )
        if not full_tree:
            logger.debug("scoped reindex: catalog hash covers all known paths")
        return catalog_hash

    async def _refresh_snapshot(self, *, full_tree: bool) -> str:
        """No-change path still records the snapshot so `index()` is idempotent."""
        catalog_hash = await self._write_snapshot(full_tree=full_tree)
        await self._session.commit()
        return catalog_hash
