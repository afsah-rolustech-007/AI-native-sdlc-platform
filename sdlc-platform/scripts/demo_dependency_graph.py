"""Print the fixture import graph and an impact set.

  uv run python scripts/demo_dependency_graph.py
"""

from __future__ import annotations

from pathlib import Path

from repo_intel.graph.networkx_client import NetworkXClient

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "source_tree"


def main() -> None:
    client = NetworkXClient(FIXTURE)
    stats = client.build()
    print(f"repo_root={FIXTURE}")
    print(
        f"files={stats.file_nodes} symbols={stats.symbol_nodes} "
        f"import_edges={stats.import_edges} call_edges={stats.call_edges}\n"
    )
    print("import adjacency (A → B means A depends on B):")
    for path, deps in client.adjacency_list().items():
        shown = ", ".join(deps) if deps else "(none)"
        print(f"  {path}: {shown}")

    symbol = "src/auth.py::validate_token"
    print(f"\nget_callers({symbol!r}, depth=1):")
    for item in client.get_callers(symbol, depth=1):
        print(f"  {item.id}")

    impact = client.get_impact_set(["src/auth.py"])
    print("\nget_impact_set(['src/auth.py']):")
    print(f"  changed_files={impact.changed_files}")
    print(f"  affected_files={impact.affected_files}")
    print(f"  affected_symbols={impact.affected_symbols}")
    print(f"  depth={impact.depth}")


if __name__ == "__main__":
    main()
