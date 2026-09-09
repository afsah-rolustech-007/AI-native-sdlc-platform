"""AST-derived architecture summary (Phase 03 Section 06, §G.7).

Everything here comes from Section 01 symbols and Section 03 import edges.
No LLM, no heuristic prose — the output is deterministic for a given working tree,
so it can be diffed and cached.

"Service" = first path segment (or `<root>` for top-level files). That is a crude
but honest proxy for module ownership in a monorepo; a real service registry is
deferred.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

from repo_intel.models import Symbol

# Filenames that usually start a process or mount a router.
_ENTRY_STEMS = frozenset({"main", "app", "cli", "server", "index", "__main__", "worker"})

# Path segments that mark an HTTP/RPC edge of the system.
_API_SEGMENTS = frozenset({"api", "routes", "router", "routers", "endpoints", "handlers"})

# Path segments that usually hold persistence definitions.
_DB_SEGMENTS = frozenset({"models", "tables", "schema", "schemas", "entities", "db"})

_LANGUAGE_BY_SUFFIX = {"py": "python", "ts": "typescript", "tsx": "tsx"}


def service_of(file_path: str) -> str:
    """First path segment; top-level files are grouped under `<root>`."""
    head, _, tail = file_path.partition("/")
    return head if tail else "<root>"


def _language_of(file_path: str) -> str:
    return _LANGUAGE_BY_SUFFIX.get(file_path.rsplit(".", 1)[-1], "unknown")


def _is_entry_point(file_path: str) -> bool:
    stem = file_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return stem in _ENTRY_STEMS


def _has_segment(file_path: str, segments: frozenset[str]) -> bool:
    """Match a directory name OR the file stem, so `storage/models.py` counts."""
    parts = file_path.split("/")
    candidates = [*parts[:-1], parts[-1].rsplit(".", 1)[0]]
    return any(part.lower() in segments for part in candidates)


def rank_files_by_in_degree(adjacency: Mapping[str, Sequence[str]]) -> list[tuple[str, int]]:
    """Files sorted by how many other files import them (most depended-on first).

    This is the placeholder behind `get_aider_repo_map`. Phase 12 replaces it with
    Aider-style PageRank; in-degree is the zero-tuning stand-in.
    """
    in_degree: Counter[str] = Counter()
    for source, targets in adjacency.items():
        in_degree.setdefault(source, 0)
        for target in targets:
            in_degree[target] += 1
    return sorted(in_degree.items(), key=lambda item: (-item[1], item[0]))


def build_architecture_summary(
    repo_root: str,
    symbols: Sequence[Symbol],
    adjacency: Mapping[str, Sequence[str]],
) -> dict[str, object]:
    """Group symbols + import edges into the §G.7 shape. Pure function, easy to test."""
    files = sorted({*adjacency, *(symbol.file_path for symbol in symbols)})
    symbols_by_file: dict[str, list[Symbol]] = defaultdict(list)
    for symbol in symbols:
        symbols_by_file[symbol.file_path].append(symbol)

    in_degree = dict(rank_files_by_in_degree(adjacency))
    importers_by_file: dict[str, set[str]] = defaultdict(set)
    for source, targets in adjacency.items():
        for target in targets:
            importers_by_file[target].add(source)

    service_map: dict[str, object] = {}
    cross_service_deps: list[dict[str, str]] = []
    for service in sorted({service_of(path) for path in files}):
        owned = [path for path in files if service_of(path) == service]
        dependencies: set[str] = set()
        for path in owned:
            for target in adjacency.get(path, ()):
                other = service_of(target)
                if other != service:
                    dependencies.add(other)
                    cross_service_deps.append({"from": path, "to": target})
        key_symbols = [
            symbol.id
            for symbol in sorted(
                (s for path in owned for s in symbols_by_file.get(path, ())),
                key=lambda s: (-in_degree.get(s.file_path, 0), s.file_path, s.start_line),
            )
            if symbol.kind in {"class", "function"}
        ][:10]
        service_map[service] = {
            "files": len(owned),
            "entry_points": [path for path in owned if _is_entry_point(path)],
            "key_symbols": key_symbols,
            "dependencies": sorted(dependencies),
            "tech_stack": sorted({_language_of(path) for path in owned}),
        }

    shared_modules = sorted(
        path
        for path, importers in importers_by_file.items()
        if len({service_of(importer) for importer in importers}) > 1
    )
    database_entities = sorted(
        symbol.id
        for symbol in symbols
        if symbol.kind == "class" and _has_segment(symbol.file_path, _DB_SEGMENTS)
    )
    api_boundaries = sorted(path for path in files if _has_segment(path, _API_SEGMENTS))

    return {
        "repo_root": repo_root,
        "generated_by": "ast",  # never an LLM — see module docstring
        "file_count": len(files),
        "symbol_count": len(symbols),
        "services": sorted(service_map),
        "service_map": service_map,
        "shared_modules": shared_modules,
        "database_entities": database_entities,
        "api_boundaries": api_boundaries,
        "cross_service_dependencies": sorted(
            cross_service_deps, key=lambda edge: (edge["from"], edge["to"])
        ),
    }


def summary_to_json(summary: Mapping[str, object]) -> str:
    return json.dumps(summary, indent=2, sort_keys=False)
