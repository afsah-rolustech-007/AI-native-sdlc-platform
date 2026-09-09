"""Tree-sitter L1 symbol index over the local working tree.

Input is a filesystem path, never a git blob. `index_repo` writes the SHA-256
catalog that Section 05 will diff; this module does not call git.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from tree_sitter import Node, Parser, Tree

from repo_intel.exceptions import FileParseError, RepoIntelError, UnsupportedLanguageError
from repo_intel.indexers.catalog import (
    FileSnapshot,
    compute_catalog_hash,
    language_for_path,
    posix_relative,
    resolve_repo_root,
    walk_working_tree,
)
from repo_intel.indexers.node_text import node_line_range
from repo_intel.indexers.python_symbols import PY_LANGUAGE, extract_python_symbols
from repo_intel.indexers.typescript_symbols import (
    TS_LANGUAGE,
    TSX_LANGUAGE,
    extract_typescript_symbols,
)
from repo_intel.models import ExtensionParseStats, IndexStats, ParseStatus, Symbol
from repo_intel.symbol_store import (
    assert_file_fresh,
    delete_repo_index,
    get_file_symbol_rows,
    get_indexed_file,
    insert_indexed_file,
    insert_symbols,
    require_symbol,
    symbol_from_row,
    upsert_snapshot,
)

logger = logging.getLogger("sdlc.repo_intel")

_LANGUAGES = {
    "python": PY_LANGUAGE,
    "typescript": TS_LANGUAGE,
    "tsx": TSX_LANGUAGE,
}

# File-structure queries omit imports; agents want class/function lists (§G.6).
STRUCTURE_KINDS = frozenset({"module", "class", "function", "method"})


def looks_binary(content: bytes) -> bool:
    return b"\x00" in content[:8192]


def first_error_detail(node: Node) -> str:
    if node.type == "ERROR" or node.is_error or node.is_missing:
        start_line, _end = node_line_range(node)
        return f"syntax error at line {start_line}"
    for child in node.children:
        detail = first_error_detail(child)
        if detail:
            return detail
    return "syntax error"


def parse_source_and_tree(
    relative_path: str, content: bytes, language: str
) -> tuple[list[Symbol], Tree]:
    """One Tree-sitter parse. Graph edge extraction reuses this tree (no second parser)."""
    grammar = _LANGUAGES.get(language)
    if grammar is None:
        raise UnsupportedLanguageError(relative_path)
    if looks_binary(content):
        raise FileParseError(relative_path, "file contains NUL bytes")
    tree = Parser(grammar).parse(content)
    if tree.root_node.has_error:
        raise FileParseError(relative_path, first_error_detail(tree.root_node))
    if language == "python":
        return extract_python_symbols(relative_path, content, tree), tree
    if language in {"typescript", "tsx"}:
        return extract_typescript_symbols(relative_path, content, tree, grammar=language), tree
    raise UnsupportedLanguageError(relative_path)


def parse_source(relative_path: str, content: bytes, language: str) -> list[Symbol]:
    """Parse already-read file bytes. Raises FileParseError on ERROR trees."""
    symbols, _tree = parse_source_and_tree(relative_path, content, language)
    return symbols


def parse_file(path: Path | str, *, relative_path: str | None = None) -> list[Symbol]:
    """Parse one working-tree file into `Symbol` rows (not persisted)."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(file_path)
    rel = relative_path or (file_path.as_posix() if not file_path.is_absolute() else file_path.name)
    rel = rel.replace("\\", "/")
    language = language_for_path(file_path)
    if language is None:
        raise UnsupportedLanguageError(rel)
    content = file_path.read_bytes()
    return parse_source(rel, content, language)


def _extension_stats(
    per_extension: dict[str, ExtensionParseStats], extension: str
) -> ExtensionParseStats:
    stats = per_extension.get(extension)
    if stats is None:
        stats = ExtensionParseStats(extension=extension)
        per_extension[extension] = stats
    return stats


def _record_status(
    snapshot: FileSnapshot,
    status: ParseStatus,
    per_extension: dict[str, ExtensionParseStats],
    counters: dict[str, int],
) -> None:
    suffix = Path(snapshot.relative_path).suffix.lower() or "(none)"
    ext = _extension_stats(per_extension, suffix)
    if status == "ok":
        ext.parsed_ok += 1
        counters["ok"] += 1
    elif status == "parse_error":
        ext.parse_error += 1
        counters["parse_error"] += 1
    else:
        ext.skipped += 1
        counters["skipped"] += 1


def _parse_snapshot(snapshot: FileSnapshot) -> tuple[list[Symbol], ParseStatus]:
    try:
        symbols = parse_source(snapshot.relative_path, snapshot.content, snapshot.language)
        return symbols, "ok"
    except FileParseError as exc:
        logger.warning("skipping %s: %s", snapshot.relative_path, exc.detail)
        return [], "parse_error"
    except UnicodeDecodeError as exc:
        logger.warning("skipping %s: not valid UTF-8 (%s)", snapshot.relative_path, exc)
        return [], "skipped"
    except Exception:
        logger.exception("unexpected parse failure for %s; skipping file", snapshot.relative_path)
        return [], "parse_error"


async def index_repo(repo_root: Path | str, session: AsyncSession) -> IndexStats:
    """Full index of the working tree: walk, parse, replace catalog + symbols.

    Re-running this is a full rebuild for `repo_root`. Section 05 adds scoped
    `reindex` that updates only hash-changed paths.
    """
    root = resolve_repo_root(repo_root)
    snapshots = walk_working_tree(root)
    await delete_repo_index(session, root)

    per_extension: dict[str, ExtensionParseStats] = {}
    counters = {"ok": 0, "parse_error": 0, "skipped": 0}
    symbols_indexed = 0
    catalog_pairs: list[tuple[str, str]] = []

    for snapshot in snapshots:
        symbols, status = _parse_snapshot(snapshot)
        _record_status(snapshot, status, per_extension, counters)
        await insert_indexed_file(session, root, snapshot, status)
        await insert_symbols(session, root, symbols)
        catalog_pairs.append((snapshot.relative_path, snapshot.content_hash))
        symbols_indexed += len(symbols)

    catalog_hash = compute_catalog_hash(catalog_pairs)
    await upsert_snapshot(session, root, file_count=len(snapshots), catalog_hash=catalog_hash)
    await session.commit()
    return IndexStats(
        repo_root=str(root),
        files_seen=len(snapshots),
        files_parsed_ok=counters["ok"],
        files_parse_error=counters["parse_error"],
        files_skipped=counters["skipped"],
        symbols_indexed=symbols_indexed,
        catalog_hash=catalog_hash,
        per_extension=per_extension,
    )


def normalize_query_path(repo_root: Path, file_path: str) -> str:
    candidate = Path(file_path)
    if candidate.is_absolute():
        return posix_relative(repo_root, candidate)
    return file_path.replace("\\", "/")


def slice_source_lines(text: str, start_line: int, end_line: int, *, file_path: str) -> str:
    lines = text.splitlines(keepends=True)
    if start_line < 1 or end_line < start_line or end_line > len(lines):
        raise RepoIntelError(
            f"stored line range {start_line}-{end_line} does not fit "
            f"{file_path} ({len(lines)} lines). Re-index the working tree."
        )
    return "".join(lines[start_line - 1 : end_line])


async def get_file_structure(
    session: AsyncSession, repo_root: Path | str, file_path: str
) -> list[Symbol]:
    root = resolve_repo_root(repo_root)
    relative = normalize_query_path(root, file_path)
    await assert_file_fresh(session, root, relative)
    rows = await get_file_symbol_rows(session, root, relative)
    return [symbol_from_row(row) for row in rows if row.kind in STRUCTURE_KINDS]


async def get_symbol_signature(session: AsyncSession, repo_root: Path | str, symbol_id: str) -> str:
    root = resolve_repo_root(repo_root)
    symbol = await require_symbol(session, root, symbol_id)
    await assert_file_fresh(session, root, symbol.file_path)
    return symbol.signature or ""


async def get_symbol_body(session: AsyncSession, repo_root: Path | str, symbol_id: str) -> str:
    """Re-read the working-tree file after a per-path catalog hash check."""
    root = resolve_repo_root(repo_root)
    symbol = await require_symbol(session, root, symbol_id)
    await assert_file_fresh(session, root, symbol.file_path)
    disk_path = root / symbol.file_path
    text = disk_path.read_text(encoding="utf-8")
    return slice_source_lines(text, symbol.start_line, symbol.end_line, file_path=symbol.file_path)


async def get_indexed_parse_status(
    session: AsyncSession, repo_root: Path | str, file_path: str
) -> str | None:
    root = resolve_repo_root(repo_root)
    relative = normalize_query_path(root, file_path)
    row = await get_indexed_file(session, root, relative)
    return None if row is None else row.parse_status
