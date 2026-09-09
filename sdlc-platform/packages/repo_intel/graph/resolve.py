"""Turn import/call refs into graph edges. Unresolved targets are skipped, not invented."""

from __future__ import annotations

from pathlib import Path

from tree_sitter import Tree

from repo_intel.graph.python_edges import extract_python_refs
from repo_intel.graph.refs import CallRef, GraphEdge, ImportRef
from repo_intel.graph.typescript_edges import extract_typescript_refs
from repo_intel.models import Symbol

_STRUCTURE = frozenset({"class", "function", "method"})


def extract_refs(
    relative_path: str,
    source: bytes,
    tree: Tree,
    symbols: list[Symbol],
    language: str,
) -> tuple[list[ImportRef], list[CallRef]]:
    if language == "python":
        return extract_python_refs(relative_path, source, tree, symbols)
    if language in {"typescript", "tsx"}:
        return extract_typescript_refs(relative_path, source, tree, symbols, grammar=language)
    return [], []


def resolve_edges(
    imports: list[ImportRef],
    calls: list[CallRef],
    *,
    known_files: set[str],
    symbols_by_file: dict[str, list[Symbol]],
) -> list[GraphEdge]:
    """Map refs onto files/symbols that exist in this working tree.

    Stdlib, packages, builtins, getattr, and missing files produce no edge.
    """
    import_map, file_edges = _resolve_imports(imports, known_files, symbols_by_file)
    call_edges = _resolve_calls(calls, import_map, symbols_by_file)
    return _dedupe([*file_edges, *call_edges])


def resolve_python_module(
    origin_file: str, module: str, relative_level: int, known_files: set[str]
) -> str | None:
    if "," in module:
        return None
    if relative_level:
        parts = _parent_parts(origin_file)
        up = relative_level - 1
        if up > len(parts):
            return None
        if up:
            parts = parts[:-up]
        if module:
            parts.extend(module.split("."))
        return _existing_py("/".join(parts), known_files)
    if not module:
        return None
    return _existing_py(module.replace(".", "/"), known_files)


def resolve_ts_specifier(origin_file: str, specifier: str, known_files: set[str]) -> str | None:
    if not specifier.startswith("."):
        return None
    base = Path(origin_file).parent / specifier
    normalized = Path(*base.parts).as_posix()
    for suffix in (".ts", ".tsx", ".js"):
        candidate = normalized + suffix
        if candidate in known_files:
            return candidate
    for index in ("/index.ts", "/index.tsx"):
        candidate = normalized + index
        if candidate in known_files:
            return candidate
    return None


def _resolve_imports(
    imports: list[ImportRef],
    known_files: set[str],
    symbols_by_file: dict[str, list[Symbol]],
) -> tuple[dict[str, dict[str, Symbol]], list[GraphEdge]]:
    import_map: dict[str, dict[str, Symbol]] = {}
    edges: list[GraphEdge] = []
    for ref in imports:
        target = _resolve_import_file(ref, known_files)
        if target is None:
            continue
        edges.append(
            GraphEdge(
                source=ref.origin_file,
                target=target,
                edge_type="import",
                origin_file=ref.origin_file,
            )
        )
        file_map = import_map.setdefault(ref.origin_file, {})
        target_symbols = symbols_by_file.get(target, [])
        if any(local == "*" for local, _original in ref.names):
            for symbol in target_symbols:
                if symbol.kind in _STRUCTURE:
                    file_map[symbol.name] = symbol
            continue
        for local, original in ref.names:
            match = _symbol_named(target_symbols, original)
            if match is not None:
                file_map[local] = match
    return import_map, edges


def _resolve_import_file(ref: ImportRef, known_files: set[str]) -> str | None:
    if "/" in ref.module or ref.module.startswith("."):
        return resolve_ts_specifier(ref.origin_file, ref.module, known_files)
    return resolve_python_module(ref.origin_file, ref.module, ref.relative_level, known_files)


def _resolve_calls(
    calls: list[CallRef],
    import_map: dict[str, dict[str, Symbol]],
    symbols_by_file: dict[str, list[Symbol]],
) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    for ref in calls:
        callee = _resolve_callee(ref, import_map, symbols_by_file)
        if callee is None or callee.id == ref.caller_id:
            continue
        edges.append(
            GraphEdge(
                source=ref.caller_id,
                target=callee.id,
                edge_type="call",
                origin_file=ref.origin_file,
            )
        )
    return edges


def _resolve_callee(
    ref: CallRef,
    import_map: dict[str, dict[str, Symbol]],
    symbols_by_file: dict[str, list[Symbol]],
) -> Symbol | None:
    imported = import_map.get(ref.origin_file, {})
    local = symbols_by_file.get(ref.origin_file, [])
    if ref.object_name:
        owner = imported.get(ref.object_name) or _symbol_named(local, ref.object_name)
        if owner is None:
            return None
        return _symbol_qualified(
            symbols_by_file.get(owner.file_path, []), owner.name, ref.simple_name
        )
    if ref.simple_name in imported:
        return imported[ref.simple_name]
    return _symbol_named(local, ref.simple_name)


def _symbol_named(symbols: list[Symbol], name: str) -> Symbol | None:
    for kind in ("function", "class", "method"):
        matches = [s for s in symbols if s.kind == kind and s.name == name]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None
    return None


def _symbol_qualified(symbols: list[Symbol], owner: str, name: str) -> Symbol | None:
    suffix = f".{name}"
    matches = [
        s
        for s in symbols
        if s.kind in _STRUCTURE and s.name == name and (s.id.endswith(f"::{owner}{suffix}"))
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _existing_py(stem: str, known_files: set[str]) -> str | None:
    if not stem:
        return None
    py_file = f"{stem}.py"
    if py_file in known_files:
        return py_file
    init = f"{stem}/__init__.py"
    if init in known_files:
        return init
    return None


def _parent_parts(origin_file: str) -> list[str]:
    parent = Path(origin_file).parent.as_posix()
    if parent in {"", "."}:
        return []
    return parent.split("/")


def _dedupe(edges: list[GraphEdge]) -> list[GraphEdge]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[GraphEdge] = []
    for edge in edges:
        key = (edge.source, edge.target, edge.edge_type)
        if key in seen:
            continue
        seen.add(key)
        unique.append(edge)
    return unique
