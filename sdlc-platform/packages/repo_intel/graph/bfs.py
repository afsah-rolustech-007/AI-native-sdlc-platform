"""Bounded-depth BFS over a typed subset of DiGraph edges."""

from __future__ import annotations

from collections import deque

import networkx as nx


def bounded_bfs(
    graph: nx.DiGraph,
    start_nodes: list[str],
    *,
    depth: int,
    reverse: bool,
    edge_type: str,
) -> list[str]:
    """Nodes reachable in 1..depth hops along `edge_type` edges. Starts are excluded.

    `reverse=True` walks incoming edges (callers / import dependents).
    """
    if depth < 1:
        raise ValueError("depth must be a positive integer")
    found: list[str] = []
    seen = set(start_nodes)
    queue: deque[tuple[str, int]] = deque((node, 0) for node in start_nodes)
    while queue:
        node, hops = queue.popleft()
        if hops >= depth:
            continue
        neighbors = graph.predecessors(node) if reverse else graph.successors(node)
        for neighbor in neighbors:
            src, dst = (neighbor, node) if reverse else (node, neighbor)
            if graph.edges[src, dst].get("type") != edge_type:
                continue
            if neighbor in seen:
                continue
            seen.add(neighbor)
            found.append(neighbor)
            queue.append((neighbor, hops + 1))
    return found
