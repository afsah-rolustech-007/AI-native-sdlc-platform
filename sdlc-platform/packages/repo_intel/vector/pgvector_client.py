"""Main entry point for semantic code search (Phase 03 Section 04).

Flow:
  1. Read working-tree files → build chunks (see vector/chunks.py).
  2. Call ModelAdapter.embed() — never a provider SDK directly.
  3. Store vectors in Postgres pgvector table `code_embeddings`.
  4. Search: embed the query, nearest neighbors, overlapping-span collapse.

Updates:
  - index_working_tree()           skip unchanged content_hash (default).
  - index_working_tree(rebuild=True)  wipe and re-embed everything.
  - reembed_paths([...])           only listed files via catalog.read_paths.

Section 05 will call reembed_paths after catalog diff. This file does not
raise StaleIndexError yet. Ranking/fusion policy is Section 06.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from model_adapters.base import ModelAdapter, Vector
from repo_intel.exceptions import (
    EmbeddingDimensionError,
    EmbeddingIndexError,
    EmbeddingsNotIndexedError,
)
from repo_intel.indexers.catalog import (
    FileSnapshot,
    read_paths,
    resolve_repo_root,
    walk_working_tree,
)
from repo_intel.models import CodeChunk, EmbeddingIndexStats
from repo_intel.vector.chunks import chunks_from_snapshot, dedupe_overlapping_spans
from repo_intel.vector.constants import EMBED_BATCH_SIZE, EMBEDDING_DIMENSIONS, SEARCH_OVERFETCH
from repo_intel.vector.store import (
    cosine_search,
    count_embeddings,
    delete_file_embeddings,
    delete_missing_symbol_embeddings,
    delete_repo_embeddings,
    hashes_for_repo,
    insert_embeddings,
    upsert_embeddings,
)

logger = logging.getLogger("sdlc.repo_intel")


class PgvectorClient:
    """Embed and search symbol-bounded chunks for one repo_root on disk."""

    def __init__(
        self,
        session: AsyncSession,
        adapter: ModelAdapter,
        repo_root: Path | str | None = None,
        *,
        batch_size: int = EMBED_BATCH_SIZE,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        self._session = session
        self._adapter = adapter
        self.repo_root = resolve_repo_root(repo_root) if repo_root is not None else None
        self.batch_size = batch_size

    async def index_working_tree(
        self,
        repo_root: Path | str | None = None,
        *,
        rebuild: bool = False,
    ) -> EmbeddingIndexStats:
        """Index every eligible file. Unchanged content_hash is skipped unless rebuild=True."""
        root = self._resolve(repo_root)
        snapshots = walk_working_tree(root)
        if rebuild:
            return await self._rebuild_all(root, snapshots)
        return await self._upsert_snapshots(root, snapshots, delete_missing_files=True)

    async def reembed_paths(self, relative_paths: Sequence[str]) -> EmbeddingIndexStats:
        """Incremental update for specific files only (Section 05 calls this).

        Pass every old and new path of a move in one call so identity stays consistent.
        Other files in the repo are not read or re-embedded.
        """
        root = self._require_root()
        wanted = {path.replace("\\", "/") for path in relative_paths if path.strip()}
        if not wanted:
            return EmbeddingIndexStats(
                repo_root=str(root),
                chunks_embedded=0,
                chunks_skipped_unchanged=0,
                files_seen=0,
            )
        snapshots = read_paths(root, list(wanted))
        return await self._upsert_snapshots(
            root,
            snapshots,
            delete_missing_files=False,
            treat_absent_as_deleted=wanted,
        )

    async def delete_path(self, relative_path: str) -> None:
        """Remove every embedding for a file that was deleted from the working tree."""
        root = self._require_root()
        path = relative_path.replace("\\", "/")
        try:
            await delete_file_embeddings(self._session, str(root), path)
            await self._session.commit()
        except Exception as exc:
            await self._session.rollback()
            raise EmbeddingIndexError(f"delete_path failed for {path}: {exc}") from exc

    async def search_concepts(
        self,
        query: str,
        top_k: int = 5,
        *,
        kinds: Sequence[str] | None = None,
        paths: Sequence[str] | None = None,
        min_score: float | None = None,
    ) -> list[CodeChunk]:
        """Natural-language search. Filters are optional plumbing for Section 06."""
        return await self._search(query, top_k, kinds=kinds, paths=paths, min_score=min_score)

    async def find_similar_implementations(
        self,
        code: str,
        top_k: int = 3,
        *,
        kinds: Sequence[str] | None = None,
        paths: Sequence[str] | None = None,
        min_score: float | None = None,
    ) -> list[CodeChunk]:
        """Same cosine path as search_concepts; query is a code snippet."""
        return await self._search(code, top_k, kinds=kinds, paths=paths, min_score=min_score)

    async def _rebuild_all(self, root: Path, snapshots: list[FileSnapshot]) -> EmbeddingIndexStats:
        chunks: list[CodeChunk] = []
        for snapshot in snapshots:
            file_chunks = chunks_from_snapshot(snapshot)
            if not file_chunks:
                logger.info(
                    "no embeddable symbols in %s (parse skip or no class/function/method)",
                    snapshot.relative_path,
                )
            chunks.extend(file_chunks)
        try:
            vectors = self._embed_texts([chunk.chunk_text for chunk in chunks])
        except EmbeddingIndexError:
            raise
        except Exception as exc:
            raise EmbeddingIndexError(f"embedding the working tree failed: {exc}") from exc
        try:
            await delete_repo_embeddings(self._session, str(root))
            await insert_embeddings(
                self._session, str(root), list(zip(chunks, vectors, strict=True))
            )
            await self._session.commit()
        except EmbeddingIndexError:
            raise
        except Exception as exc:
            await self._session.rollback()
            raise EmbeddingIndexError(f"writing code_embeddings failed: {exc}") from exc
        return EmbeddingIndexStats(
            repo_root=str(root),
            chunks_embedded=len(chunks),
            chunks_skipped_unchanged=0,
            files_seen=len(snapshots),
        )

    async def apply_chunks(
        self,
        chunks_by_file: Mapping[str, list[CodeChunk]],
        *,
        deleted_paths: Sequence[str] = (),
        commit: bool = True,
    ) -> EmbeddingIndexStats:
        """Upsert already-parsed chunks; Section 05 uses this to avoid a second parse.

        `commit=False` leaves the transaction open so the caller can commit symbols,
        embeddings, and the catalog together (a partial reindex must not be durable).
        """
        root = self._require_root()
        return await self._apply(
            root,
            {path: list(chunks) for path, chunks in chunks_by_file.items()},
            delete_files=[path.replace("\\", "/") for path in deleted_paths],
            commit=commit,
        )

    async def _upsert_snapshots(
        self,
        root: Path,
        snapshots: list[FileSnapshot],
        *,
        delete_missing_files: bool,
        treat_absent_as_deleted: set[str] | None = None,
    ) -> EmbeddingIndexStats:
        on_disk = {snapshot.relative_path: snapshot for snapshot in snapshots}
        chunks_by_file = {path: chunks_from_snapshot(snap) for path, snap in on_disk.items()}

        delete_files: list[str] = []
        if delete_missing_files:
            try:
                existing = await hashes_for_repo(self._session, str(root))
            except Exception as exc:
                raise EmbeddingIndexError(f"reading code_embeddings failed: {exc}") from exc
            delete_files.extend(path for path in existing if path not in on_disk)
        if treat_absent_as_deleted is not None:
            delete_files.extend(path for path in treat_absent_as_deleted if path not in on_disk)
        return await self._apply(root, chunks_by_file, delete_files=delete_files, commit=True)

    async def _apply(
        self,
        root: Path,
        chunks_by_file: dict[str, list[CodeChunk]],
        *,
        delete_files: list[str],
        commit: bool,
    ) -> EmbeddingIndexStats:
        """Shared write path: skip unchanged hashes, embed the rest, then one DB pass."""
        try:
            existing = await hashes_for_repo(self._session, str(root))
        except Exception as exc:
            raise EmbeddingIndexError(f"reading code_embeddings failed: {exc}") from exc

        skipped = 0
        to_embed: list[CodeChunk] = []
        keep_by_file: dict[str, set[str]] = {}
        for path, chunks in chunks_by_file.items():
            if not chunks:
                logger.debug("no embeddable symbols in %s", path)
            keep_by_file[path] = {chunk.symbol_id for chunk in chunks if chunk.symbol_id}
            file_hashes = existing.get(path, {})
            for chunk in chunks:
                if file_hashes.get(chunk.symbol_id or "") == chunk.content_hash:
                    skipped += 1
                else:
                    to_embed.append(chunk)

        # Embed first: a provider failure must leave the previous index untouched.
        try:
            vectors = self._embed_texts([chunk.chunk_text for chunk in to_embed])
        except EmbeddingIndexError:
            raise
        except Exception as exc:
            raise EmbeddingIndexError(f"embedding failed: {exc}") from exc

        try:
            for path in delete_files:
                await delete_file_embeddings(self._session, str(root), path)
            for path, keep in keep_by_file.items():
                await delete_missing_symbol_embeddings(self._session, str(root), path, keep)
            await upsert_embeddings(
                self._session, str(root), list(zip(to_embed, vectors, strict=True))
            )
            if commit:
                await self._session.commit()
        except EmbeddingIndexError:
            raise
        except Exception as exc:
            await self._session.rollback()
            raise EmbeddingIndexError(f"writing code_embeddings failed: {exc}") from exc

        if to_embed or delete_files:
            logger.info(
                "embeddings applied: %d embedded, %d unchanged, %d files deleted",
                len(to_embed),
                skipped,
                len(delete_files),
            )
        return EmbeddingIndexStats(
            repo_root=str(root),
            chunks_embedded=len(to_embed),
            chunks_skipped_unchanged=skipped,
            files_seen=len(chunks_by_file),
        )

    async def _search(
        self,
        text: str,
        top_k: int,
        *,
        kinds: Sequence[str] | None,
        paths: Sequence[str] | None,
        min_score: float | None,
    ) -> list[CodeChunk]:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("query must be a non-empty string")
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        if min_score is not None and not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be between 0 and 1")
        root = self._require_root()
        try:
            n = await count_embeddings(self._session, str(root))
        except Exception as exc:
            raise EmbeddingIndexError(f"reading code_embeddings failed: {exc}") from exc
        if n == 0:
            raise EmbeddingsNotIndexedError(str(root))
        vectors = self._embed_texts([cleaned])
        fetch_k = max(top_k * SEARCH_OVERFETCH, top_k)
        try:
            hits = await cosine_search(
                self._session,
                str(root),
                vectors[0],
                fetch_k,
                kinds=kinds,
                paths=paths,
                min_score=min_score,
            )
        except EmbeddingIndexError:
            raise
        except Exception as exc:
            raise EmbeddingIndexError(f"pgvector cosine search failed: {exc}") from exc
        return dedupe_overlapping_spans(hits, top_k)

    def _embed_texts(self, texts: list[str]) -> list[Vector]:
        """Call ModelAdapter.embed() in batches; validate vector width."""
        if not texts:
            return []
        out: list[Vector] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            try:
                vectors = self._adapter.embed(batch)
            except EmbeddingDimensionError:
                raise
            except Exception as exc:
                raise EmbeddingIndexError(f"ModelAdapter.embed() failed: {exc}") from exc
            if len(vectors) != len(batch):
                raise EmbeddingIndexError(
                    f"ModelAdapter.embed() returned {len(vectors)} vectors for {len(batch)} texts"
                )
            for vector in vectors:
                _assert_dimension(vector)
            out.extend(vectors)
        return out

    def _resolve(self, repo_root: Path | str | None) -> Path:
        if repo_root is not None:
            self.repo_root = resolve_repo_root(repo_root)
            return self.repo_root
        return self._require_root()

    def _require_root(self) -> Path:
        if self.repo_root is None:
            raise ValueError("repo_root is required")
        return self.repo_root


def _assert_dimension(vector: Vector) -> None:
    if not vector:
        raise EmbeddingDimensionError(0, EMBEDDING_DIMENSIONS)
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise EmbeddingDimensionError(len(vector), EMBEDDING_DIMENSIONS)
