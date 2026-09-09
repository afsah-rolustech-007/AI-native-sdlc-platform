"""In-process NetworkX dependency/call graph over the local working tree.

Edge direction (fixed so Neo4j can copy the same meaning later):
  import:  A.py → B.py     means A imports / depends on B
  call:    foo → bar       means foo calls bar

get_dependencies / get_callees walk outgoing edges.
get_dependents / get_callers / get_impact_set walk incoming edges.

Section 05: when B.py changes, call replace_file() which drops only edges whose
origin_file is B.py. Incoming import edges from A.py stay. Do not re-parse A.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import networkx as nx
from tree_sitter import Tree

from repo_intel.exceptions import (
    FileNotIndexedError,
    FileParseError,
    GraphNotBuiltError,
    SymbolNotFoundError,
)
from repo_intel.graph.bfs import bounded_bfs
from repo_intel.graph.refs import GraphEdge
from repo_intel.graph.resolve import extract_refs, resolve_edges
from repo_intel.indexers.catalog import FileSnapshot, resolve_repo_root, walk_working_tree
from repo_intel.indexers.treesitter import parse_source_and_tree
from repo_intel.models import ImpactSet, Symbol

DEFAULT_IMPACT_DEPTH = 2
_STRUCTURE = frozenset({"class", "function", "method", "module"})


@dataclass(frozen=True)
class GraphStats:
    repo_root: str
    file_nodes: int
    symbol_nodes: int
    import_edges: int
    call_edges: int


class NetworkXClient:
    """Build and query the L2 graph. Holds the DiGraph in memory (not Postgres)."""

    def __init__(
        self,
        repo_root: Path | str | None = None,
        *,
        impact_depth: int = DEFAULT_IMPACT_DEPTH,
    ) -> None:
        if impact_depth < 1:
            raise ValueError("impact_depth must be a positive integer")
        self.repo_root = resolve_repo_root(repo_root) if repo_root is not None else None
        self.impact_depth = impact_depth
        self._graph = nx.DiGraph()
        self._built = False
        self._symbols: dict[str, Symbol] = {}
        self._files: set[str] = set()

    def build(self, root_path: Path | str | None = None) -> GraphStats:
        """Full rebuild from the working tree. Same eligible files as Section 01."""
        root = resolve_repo_root(root_path) if root_path is not None else self.repo_root
        if root is None:
            raise ValueError("repo_root is required")
        self.repo_root = root
        snapshots = walk_working_tree(root)
        parsed: list[tuple[FileSnapshot, list[Symbol], Tree | None]] = []
        symbols_by_file: dict[str, list[Symbol]] = {}
        for snapshot in snapshots:
            symbols, tree = _try_parse(snapshot)
            parsed.append((snapshot, symbols, tree))
            symbols_by_file[snapshot.relative_path] = symbols

        known = {item.relative_path for item in snapshots}
        all_imports = []
        all_calls = []
        for snapshot, symbols, tree in parsed:
            if tree is None:
                continue
            imports, calls = extract_refs(
                snapshot.relative_path, snapshot.content, tree, symbols, snapshot.language
            )
            all_imports.extend(imports)
            all_calls.extend(calls)
        edges = resolve_edges(
            all_imports, all_calls, known_files=known, symbols_by_file=symbols_by_file
        )
        self._replace_graph(known, symbols_by_file, edges)
        return self._stats(str(root))

    @property
    def is_built(self) -> bool:
        """False until build() ran. Section 05 hydrates a cold graph before querying."""
        return self._built

    def replace_file(self, relative_path: str, content: bytes, language: str) -> None:
        """Section 05 modify/create: replace outgoing edges from this file only."""
        try:
            symbols, tree = parse_source_and_tree(relative_path, content, language)
        except FileParseError:
            symbols, tree = [], None
        self.replace_file_parsed(relative_path, content, language, symbols, tree)

    def replace_file_parsed(
        self,
        relative_path: str,
        content: bytes,
        language: str,
        symbols: list[Symbol],
        tree: Tree | None,
    ) -> None:
        """Same as replace_file but reuses Section 05's single Tree-sitter parse.

        `tree=None` means the file failed to parse: we keep the file node and drop
        its outgoing edges, so a broken file stops claiming stale dependencies.
        """
        self._require_built()
        self._files.add(relative_path)
        self._add_file_node(relative_path)
        self._drop_outgoing(relative_path)
        self._drop_orphaned_local_symbols(relative_path, {s.id for s in symbols})
        for symbol in symbols:
            self._add_symbol_node(symbol)
        if tree is None:
            return
        imports, calls = extract_refs(relative_path, content, tree, symbols, language)
        symbols_by_file = self._symbols_by_file()
        symbols_by_file[relative_path] = symbols
        edges = resolve_edges(
            imports, calls, known_files=set(self._files), symbols_by_file=symbols_by_file
        )
        for edge in edges:
            self._add_edge(edge)

    def remove_file(self, relative_path: str) -> None:
        """Section 05 delete: drop this file's nodes and every incident edge."""
        self._require_built()
        if relative_path not in self._files and relative_path not in self._graph:
            return
        to_remove = [relative_path]
        to_remove.extend(
            node
            for node, data in self._graph.nodes(data=True)
            if data.get("kind") == "symbol" and data.get("file_path") == relative_path
        )
        self._graph.remove_nodes_from([n for n in to_remove if n in self._graph])
        self._files.discard(relative_path)
        self._symbols = {
            sid: symbol
            for sid, symbol in self._symbols.items()
            if symbol.file_path != relative_path
        }

    def get_callers(self, symbol_id: str, depth: int = 1) -> list[Symbol]:
        self._require_symbol(symbol_id)
        ids = bounded_bfs(self._graph, [symbol_id], depth=depth, reverse=True, edge_type="call")
        return self._symbols_for(ids)

    def get_callees(self, symbol_id: str, depth: int = 1) -> list[Symbol]:
        self._require_symbol(symbol_id)
        ids = bounded_bfs(self._graph, [symbol_id], depth=depth, reverse=False, edge_type="call")
        return self._symbols_for(ids)

    def get_dependencies(self, file_path: str) -> list[str]:
        path = self._require_file(file_path)
        found = bounded_bfs(self._graph, [path], depth=1, reverse=False, edge_type="import")
        return sorted(found)

    def get_dependents(self, file_path: str) -> list[str]:
        path = self._require_file(file_path)
        found = bounded_bfs(self._graph, [path], depth=1, reverse=True, edge_type="import")
        return sorted(found)

    def get_impact_set(self, changed_files: list[str], *, depth: int | None = None) -> ImpactSet:
        """BFS along import dependents. This is a query, not a re-index."""
        self._require_built()
        if not changed_files:
            raise ValueError("changed_files must not be empty")
        hop = depth if depth is not None else self.impact_depth
        starts = [self._require_file(path) for path in changed_files]
        affected = bounded_bfs(self._graph, starts, depth=hop, reverse=True, edge_type="import")
        affected_files = sorted(path for path in affected if path not in starts)
        affected_symbols = sorted(
            symbol.id
            for symbol in self._symbols.values()
            if symbol.file_path in affected_files and symbol.kind in _STRUCTURE
        )
        return ImpactSet(
            changed_files=starts,
            affected_files=affected_files,
            affected_symbols=affected_symbols,
            depth=hop,
        )

    def adjacency_list(self) -> dict[str, list[str]]:
        """Human-readable import graph for the Section 03 demo."""
        self._require_built()
        out: dict[str, list[str]] = {}
        for node in sorted(self._files):
            deps = sorted(
                dest
                for _, dest, data in self._graph.out_edges(node, data=True)
                if data.get("type") == "import"
            )
            out[node] = deps
        return out

    def _replace_graph(
        self,
        known: set[str],
        symbols_by_file: dict[str, list[Symbol]],
        edges: list[GraphEdge],
    ) -> None:
        self._graph = nx.DiGraph()
        self._symbols = {}
        self._files = set(known)
        for path in known:
            self._add_file_node(path)
            for symbol in symbols_by_file.get(path, []):
                self._add_symbol_node(symbol)
        for edge in edges:
            self._add_edge(edge)
        self._built = True

    def _add_file_node(self, path: str) -> None:
        self._graph.add_node(path, kind="file", file_path=path)

    def _add_symbol_node(self, symbol: Symbol) -> None:
        self._symbols[symbol.id] = symbol
        self._graph.add_node(symbol.id, kind="symbol", file_path=symbol.file_path, symbol=symbol)

    def _add_edge(self, edge: GraphEdge) -> None:
        if edge.source not in self._graph or edge.target not in self._graph:
            return
        self._graph.add_edge(
            edge.source, edge.target, type=edge.edge_type, origin_file=edge.origin_file
        )

    def _drop_outgoing(self, relative_path: str) -> None:
        doomed = [
            (src, dst)
            for src, dst, data in self._graph.edges(data=True)
            if data.get("origin_file") == relative_path
        ]
        self._graph.remove_edges_from(doomed)

    def _drop_orphaned_local_symbols(self, relative_path: str, keep_ids: set[str]) -> None:
        """Remove this file's symbols that the new parse dropped and nobody else points at.

        Incoming edges keep their target node so A.py is not re-parsed (Section 05).
        """
        stale = [
            node
            for node, data in list(self._graph.nodes(data=True))
            if data.get("kind") == "symbol"
            and data.get("file_path") == relative_path
            and node not in keep_ids
            and self._graph.in_degree(node) == 0
        ]
        self._graph.remove_nodes_from(stale)
        for sid in stale:
            self._symbols.pop(sid, None)

    def _symbols_by_file(self) -> dict[str, list[Symbol]]:
        grouped: dict[str, list[Symbol]] = {path: [] for path in self._files}
        for symbol in self._symbols.values():
            grouped.setdefault(symbol.file_path, []).append(symbol)
        return grouped

    def _require_built(self) -> None:
        if not self._built:
            raise GraphNotBuiltError("call NetworkXClient.build before querying the graph")

    def _require_file(self, file_path: str) -> str:
        self._require_built()
        path = file_path.replace("\\", "/")
        if path not in self._graph or self._graph.nodes[path].get("kind") != "file":
            raise FileNotIndexedError(path)
        return path

    def _require_symbol(self, symbol_id: str) -> None:
        self._require_built()
        if symbol_id not in self._graph or self._graph.nodes[symbol_id].get("kind") != "symbol":
            raise SymbolNotFoundError(symbol_id)

    def _symbols_for(self, ids: list[str]) -> list[Symbol]:
        result: list[Symbol] = []
        for sid in ids:
            symbol = self._symbols.get(sid)
            if symbol is not None:
                result.append(symbol)
        return result

    def _stats(self, repo_root: str) -> GraphStats:
        import_edges = sum(
            1 for _s, _d, data in self._graph.edges(data=True) if data.get("type") == "import"
        )
        call_edges = sum(
            1 for _s, _d, data in self._graph.edges(data=True) if data.get("type") == "call"
        )
        return GraphStats(
            repo_root=repo_root,
            file_nodes=len(self._files),
            symbol_nodes=sum(
                1 for _n, data in self._graph.nodes(data=True) if data.get("kind") == "symbol"
            ),
            import_edges=import_edges,
            call_edges=call_edges,
        )


def _try_parse(snapshot: FileSnapshot) -> tuple[list[Symbol], Tree | None]:
    try:
        return parse_source_and_tree(snapshot.relative_path, snapshot.content, snapshot.language)
    except FileParseError:
        return [], None
