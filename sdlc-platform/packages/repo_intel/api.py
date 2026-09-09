"""RepositoryIntelligence — the only agent-facing door into repo data (Section 06, §G.6).

From Phase 04 onward, no agent imports `symbol_store`, `zoekt_client`,
`NetworkXClient`, or `PgvectorClient` directly. They call this class.

Four independent signals, deliberately NOT fused here:
  symbol   structural lookup by id/path      (Section 01, Postgres)
  lexical  exact tokens/regex                (Section 02, Zoekt)
  semantic natural-language concepts         (Section 04, pgvector)
  graph    callers/dependents/impact         (Section 03, NetworkX)

Cross-store fusion (RRF) is Phase 12. Returning each signal separately keeps the
benchmark able to attribute a miss to one signal instead of to a ranking formula.

Every read runs Section 05's whole-tree freshness check first and raises
`StaleIndexError` if the working tree drifted. `refresh=True` reindexes instead.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model_adapters.base import ModelAdapter
from repo_intel.exceptions import FileNotIndexedError, RepoIntelError
from repo_intel.indexers.incremental import IncrementalIndexer
from repo_intel.indexers.treesitter import STRUCTURE_KINDS
from repo_intel.models import (
    CodeChunk,
    ImpactSet,
    IndexStatus,
    ReindexStats,
    SearchHit,
    Symbol,
)
from repo_intel.summary import (
    build_architecture_summary,
    rank_files_by_in_degree,
    summary_to_json,
)
from repo_intel.symbol_store import (
    get_file_symbol_rows,
    list_catalog_hashes,
    require_symbol,
    symbol_from_row,
)
from repo_intel.tables import SymbolRow

logger = logging.getLogger("sdlc.repo_intel")

_PHASE_12 = "deferred to Phase 12; Section 06 returns each retrieval signal separately"
_PHASE_06 = "requires episodic data from Phase 06+; Phase 03 does not index git history"


class RepositoryIntelligence:
    """Single public class over Sections 01–05 for one working tree."""

    def __init__(
        self,
        session: AsyncSession,
        adapter: ModelAdapter,
        repo_root: Path | str | None = None,
        *,
        indexer: IncrementalIndexer | None = None,
    ) -> None:
        self._indexer = indexer or IncrementalIndexer(session, adapter, repo_root)
        self._session = session
        self.repo_root = self._indexer.repo_root

    # ---------------------------------------------------------------- indexing

    async def index(self, *, rebuild: bool = False) -> ReindexStats:
        """First index of this tree, or `rebuild=True` to wipe and start over."""
        return await self._indexer.index(rebuild=rebuild)

    async def reindex(self) -> ReindexStats:
        """Hash-diff the whole tree and update only what changed."""
        return await self._indexer.reindex()

    async def reindex_paths(self, relative_paths: Sequence[str]) -> ReindexStats:
        """Scoped update for paths an agent just wrote (both sides of a move)."""
        return await self._indexer.reindex_paths(relative_paths)

    async def index_status(self) -> IndexStatus:
        """unindexed / fresh / stale, plus the paths that drifted."""
        return await self._indexer.status()

    async def _ready(self, refresh: bool) -> None:
        """Freshness gate in front of every read. Fails closed unless asked to refresh."""
        if refresh:
            await self._indexer.reindex()
            return
        await self._indexer.assert_fresh()

    async def _ready_graph(self, refresh: bool) -> None:
        """Same gate, plus hydrate the RAM-only graph if this process restarted."""
        await self._ready(refresh)
        self._indexer.hydrate_graph()

    # -------------------------------------------------------------- structural

    async def get_symbol_signature(self, symbol_id: str, *, refresh: bool = False) -> str:
        """Signature line for a symbol. Raises SymbolNotFoundError, never returns ''."""
        await self._ready(refresh)
        symbol = await require_symbol(self._session, self.repo_root, symbol_id)
        return symbol.signature or f"{symbol.kind} {symbol.name}"

    async def get_symbol_body(self, symbol_id: str, *, refresh: bool = False) -> str:
        """Exact working-tree source of a symbol, read from disk after the freshness gate."""
        await self._ready(refresh)
        symbol = await require_symbol(self._session, self.repo_root, symbol_id)
        path = self.repo_root / symbol.file_path
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise RepoIntelError(f"could not read {symbol.file_path}: {exc}") from exc
        return "\n".join(lines[symbol.start_line - 1 : symbol.end_line])

    async def get_file_structure(
        self, file_path: str, *, refresh: bool = False
    ) -> list[Symbol]:
        """Structural symbols in one file, ordered by position. Unknown file fails closed.

        Same kind filter as Section 01: module/class/function/method, no import rows.
        """
        await self._ready(refresh)
        path = file_path.replace("\\", "/")
        rows = await get_file_symbol_rows(self._session, self.repo_root, path)
        if not rows:
            # Distinguish "not cataloged" from "cataloged but genuinely symbol-free".
            catalog = await list_catalog_hashes(self._session, self.repo_root)
            if path not in catalog:
                raise FileNotIndexedError(path)
        return [symbol_from_row(row) for row in rows if row.kind in STRUCTURE_KINDS]

    # ------------------------------------------------------------------- graph

    async def get_callers(
        self, symbol_id: str, depth: int = 1, *, refresh: bool = False
    ) -> list[Symbol]:
        await self._ready_graph(refresh)
        return self._indexer.graph.get_callers(symbol_id, depth=depth)

    async def get_callees(
        self, symbol_id: str, depth: int = 1, *, refresh: bool = False
    ) -> list[Symbol]:
        await self._ready_graph(refresh)
        return self._indexer.graph.get_callees(symbol_id, depth=depth)

    async def get_dependencies(self, file_path: str, *, refresh: bool = False) -> list[str]:
        """Files this file imports."""
        await self._ready_graph(refresh)
        return self._indexer.graph.get_dependencies(file_path)

    async def get_dependents(self, file_path: str, *, refresh: bool = False) -> list[str]:
        """Files that import this file."""
        await self._ready_graph(refresh)
        return self._indexer.graph.get_dependents(file_path)

    async def get_impact_set(
        self, changed_files: list[str], *, depth: int | None = None, refresh: bool = False
    ) -> ImpactSet:
        """Blast radius of a change. A query — it never triggers re-embedding."""
        await self._ready_graph(refresh)
        return self._indexer.graph.get_impact_set(changed_files, depth=depth)

    # ---------------------------------------------------------------- semantic

    async def search_concepts(
        self,
        query: str,
        top_k: int = 5,
        *,
        kinds: Sequence[str] | None = None,
        paths: Sequence[str] | None = None,
        min_score: float | None = None,
        refresh: bool = False,
    ) -> list[CodeChunk]:
        """Natural-language search over pgvector, with overlap dedup already applied."""
        await self._ready(refresh)
        return await self._indexer.vector.search_concepts(
            query, top_k, kinds=kinds, paths=paths, min_score=min_score
        )

    async def find_similar_implementations(
        self,
        code: str,
        top_k: int = 3,
        *,
        kinds: Sequence[str] | None = None,
        paths: Sequence[str] | None = None,
        min_score: float | None = None,
        refresh: bool = False,
    ) -> list[CodeChunk]:
        """Same cosine path, but the query is a code snippet instead of prose."""
        await self._ready(refresh)
        return await self._indexer.vector.find_similar_implementations(
            code, top_k, kinds=kinds, paths=paths, min_score=min_score
        )

    # ----------------------------------------------------------------- lexical

    async def search_codebase(
        self, query: str, top_k: int = 10, *, refresh: bool = False
    ) -> list[SearchHit]:
        """Exact tokens / regex via Zoekt. Use this for identifiers you already know.

        Not merged with `search_concepts` — see the module docstring on fusion.
        """
        await self._ready(refresh)
        return self._indexer.zoekt.search_codebase(query, top_k)

    # ------------------------------------------------------------- summary/map

    async def get_architecture_summary(self, *, refresh: bool = False) -> str:
        """Deterministic AST-derived JSON summary (§G.7). Never LLM-generated."""
        await self._ready_graph(refresh)
        symbols = await self._all_symbols()
        summary = build_architecture_summary(
            str(self.repo_root), symbols, self._indexer.graph.adjacency_list()
        )
        return summary_to_json(summary)

    async def get_aider_repo_map(
        self, scope: Sequence[str] | None = None, top_n: int = 20, *, refresh: bool = False
    ) -> list[str]:
        """Most depended-on files by raw import in-degree.

        Placeholder for Phase 12's Aider-style PageRank. In-degree has no damping
        and no query conditioning, so treat the ordering as a hint, not a ranking.
        """
        await self._ready_graph(refresh)
        ranked = rank_files_by_in_degree(self._indexer.graph.adjacency_list())
        allowed = {path.replace("\\", "/") for path in scope} if scope else None
        return [path for path, _ in ranked if allowed is None or path in allowed][:top_n]

    async def _all_symbols(self) -> list[Symbol]:
        result = await self._session.execute(
            select(SymbolRow)
            .where(SymbolRow.repo_root == str(self.repo_root))
            .order_by(SymbolRow.file_path, SymbolRow.start_line)
        )
        return [symbol_from_row(row) for row in result.scalars().all()]

    # --------------------------------------------------- declared, not yet real

    async def find_relevant_context(self, query: str, top_k: int = 10) -> list[CodeChunk]:
        """Hybrid RRF fusion across lexical + semantic + graph. Phase 12."""
        raise NotImplementedError(f"find_relevant_context is {_PHASE_12}")

    async def get_regression_history(self, symbol_id: str) -> list[dict[str, object]]:
        raise NotImplementedError(f"get_regression_history is {_PHASE_06}")

    async def get_design_decisions(self, symbol_id: str) -> list[dict[str, object]]:
        raise NotImplementedError(f"get_design_decisions is {_PHASE_06}")

    async def get_change_frequency(self, file_path: str) -> float:
        raise NotImplementedError(f"get_change_frequency is {_PHASE_06}")
