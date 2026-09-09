"""Repository Intelligence models (`final_plan.md` §G.6.1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ParseStatus = Literal["ok", "skipped", "parse_error"]


class Symbol(BaseModel):
    """Normalized Tree-sitter symbol. `id` is `{file_path}::{qualified_name}`."""

    id: str
    kind: str
    name: str
    file_path: str
    start_line: int
    end_line: int
    signature: str | None = None
    docstring: str | None = None


class ExtensionParseStats(BaseModel):
    """Per-extension counts so unsupported languages are visible, not silent."""

    extension: str
    parsed_ok: int = 0
    parse_error: int = 0
    skipped: int = 0


class SearchHit(BaseModel):
    """One lexical match. `score` is Zoekt's rank (higher is better) for Section 06 fusion."""

    file_path: str
    line: int
    snippet: str
    score: float


class ImpactSet(BaseModel):
    """Files/symbols affected by a change, via import dependents (§G.6.1)."""

    changed_files: list[str]
    affected_files: list[str]
    affected_symbols: list[str]
    depth: int


class CodeChunk(BaseModel):
    """One symbol's embeddable text + metadata (built at index time or returned from search).

    Ranking policy is Section 06's job. Fields here are identity, text, and filters.
    """

    symbol_id: str | None
    file_path: str
    kind: str
    chunk_text: str
    content_hash: str
    start_line: int
    end_line: int
    chunk_tokens: int
    truncated: bool = False
    score: float | None = None


class EmbeddingIndexStats(BaseModel):
    """Counters returned after index_working_tree or reembed_paths."""

    repo_root: str
    chunks_embedded: int  # how many embed() calls we actually made
    chunks_skipped_unchanged: int  # same content_hash as DB — no re-embed
    files_seen: int  # how many paths we processed in this run


class IndexStats(BaseModel):
    """Result of a full working-tree `index_repo` run."""

    repo_root: str
    files_seen: int
    files_parsed_ok: int
    files_parse_error: int
    files_skipped: int
    symbols_indexed: int
    catalog_hash: str
    per_extension: dict[str, ExtensionParseStats] = Field(default_factory=dict)


class CatalogDiff(BaseModel):
    """Working tree vs `indexed_files`, by SHA-256 of file bytes (Section 05).

    A rename shows up as one `deleted` plus one `created` — same-hash rename
    detection is deferred. `unchanged` files are never re-parsed or re-embedded.
    """

    created: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)
    unchanged: int = 0

    @property
    def changed_paths(self) -> list[str]:
        """Paths that must be parsed again (created + modified)."""
        return sorted({*self.created, *self.modified})

    @property
    def is_empty(self) -> bool:
        return not (self.created or self.modified or self.deleted)


class ReindexStats(BaseModel):
    """What one `index` / `reindex` / `reindex_paths` run actually did."""

    repo_root: str
    created: int = 0
    modified: int = 0
    deleted: int = 0
    unchanged: int = 0
    files_parsed: int = 0  # created + modified we ran Tree-sitter on
    files_parse_error: int = 0
    symbols_indexed: int = 0
    chunks_embedded: int = 0  # actual ModelAdapter.embed() texts
    chunks_skipped_unchanged: int = 0  # same chunk content_hash — no embed
    zoekt_rebuilt: bool = False
    graph_updated: bool = False
    elapsed_s: float = 0.0
    catalog_hash: str = ""


class IndexStatus(BaseModel):
    """Freshness of the catalog against the current working tree (Section 05).

    `state="stale"` blocks every read in Section 06 — mixed fresh/stale is not
    safe to serve as "current code".
    """

    repo_root: str
    state: Literal["unindexed", "fresh", "stale"]
    file_count: int = 0
    stale_paths: list[str] = Field(default_factory=list)
    catalog_hash: str | None = None

    @property
    def is_fresh(self) -> bool:
        return self.state == "fresh"
