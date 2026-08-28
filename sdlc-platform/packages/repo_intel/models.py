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
