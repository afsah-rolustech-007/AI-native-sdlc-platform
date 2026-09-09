"""Working-tree code graph (Phase 03 Section 03).

MVP backend is in-process NetworkX. Neo4j (Phase 11) should implement `CodeGraph`.
Agents must not import this package; Section 06's RepositoryIntelligence is the door.
"""

from repo_intel.graph.networkx_client import GraphStats, NetworkXClient
from repo_intel.graph.protocol import CodeGraph

__all__ = ["CodeGraph", "GraphStats", "NetworkXClient"]
