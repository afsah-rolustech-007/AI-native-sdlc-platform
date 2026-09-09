"""Bounded BFS and working-tree graph queries (Phase 03 Section 03)."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from repo_intel.exceptions import FileNotIndexedError, GraphNotBuiltError, SymbolNotFoundError
from repo_intel.graph.bfs import bounded_bfs
from repo_intel.graph.networkx_client import NetworkXClient
from repo_intel.graph.resolve import resolve_python_module, resolve_ts_specifier

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "source_tree"


def test_bounded_bfs_respects_depth_and_edge_type() -> None:
    graph = nx.DiGraph()
    graph.add_edge("c", "b", type="import")
    graph.add_edge("b", "a", type="import")
    graph.add_edge("x", "a", type="call")
    one = bounded_bfs(graph, ["a"], depth=1, reverse=True, edge_type="import")
    two = bounded_bfs(graph, ["a"], depth=2, reverse=True, edge_type="import")
    assert one == ["b"]
    assert set(two) == {"b", "c"}
    assert "x" not in two


def test_query_before_build_fails_closed() -> None:
    client = NetworkXClient(FIXTURE)
    with pytest.raises(GraphNotBuiltError):
        client.get_dependencies("src/auth.py")


def test_fixture_import_and_call_graph() -> None:
    client = NetworkXClient(FIXTURE)
    stats = client.build()
    assert stats.import_edges >= 1
    assert stats.call_edges >= 1

    assert client.get_dependencies("src/payments.py") == ["src/auth.py"]
    assert client.get_dependents("src/auth.py") == ["src/payments.py"]
    assert client.get_dependencies("src/uncommitted.py") == []
    assert "src/auth.ts" not in client.get_dependencies("src/models.ts")
    assert "ignored/secret.py" not in client.adjacency_list()

    callers = {symbol.id for symbol in client.get_callers("src/auth.py::validate_token")}
    assert "src/payments.py::ChargeService.charge" in callers

    callees = {symbol.id for symbol in client.get_callees("src/payments.py::ChargeService.charge")}
    assert "src/auth.py::validate_token" in callees
    assert "src/auth.py::UserService.get_user" in callees


def test_impact_set_includes_importer_not_unrelated_modules() -> None:
    client = NetworkXClient(FIXTURE, impact_depth=2)
    client.build()
    impact = client.get_impact_set(["src/auth.py"])
    assert impact.changed_files == ["src/auth.py"]
    assert impact.affected_files == ["src/payments.py"]
    assert "src/uncommitted.py" not in impact.affected_files
    assert "src/ui.tsx" not in impact.affected_files
    assert "src/models.ts" not in impact.affected_files
    assert any(sid.startswith("src/payments.py::") for sid in impact.affected_symbols)
    assert impact.depth == 2


def test_impact_set_unknown_file_fails_closed() -> None:
    client = NetworkXClient(FIXTURE)
    client.build()
    with pytest.raises(FileNotIndexedError):
        client.get_impact_set(["src/missing.py"])
    with pytest.raises(SymbolNotFoundError):
        client.get_callers("src/auth.py::does_not_exist")


def test_replace_file_does_not_require_reparse_of_importer(tmp_path: Path) -> None:
    tree = tmp_path / "repo"
    (tree / "src").mkdir(parents=True)
    (tree / "src" / "auth.py").write_text("def validate_token(t):\n    return True\n", encoding="utf-8")
    (tree / "src" / "payments.py").write_text(
        "from src.auth import validate_token\n\n"
        "def charge(token):\n    return validate_token(token)\n",
        encoding="utf-8",
    )
    client = NetworkXClient(tree)
    client.build()
    assert client.get_dependents("src/auth.py") == ["src/payments.py"]

    (tree / "src" / "auth.py").write_text(
        "def validate_token(t):\n    return True\n\ndef extra():\n    return 1\n",
        encoding="utf-8",
    )
    client.replace_file("src/auth.py", (tree / "src" / "auth.py").read_bytes(), "python")
    assert client.get_dependents("src/auth.py") == ["src/payments.py"]
    assert "src/payments.py::charge" in {
        s.id for s in client.get_callers("src/auth.py::validate_token")
    }


def test_callers_callees_respect_depth(tmp_path: Path) -> None:
    (tmp_path / "c.py").write_text("def c():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text(
        "from c import c\n\ndef b():\n    return c()\n", encoding="utf-8"
    )
    (tmp_path / "a.py").write_text(
        "from b import b\n\ndef a():\n    return b()\n", encoding="utf-8"
    )
    client = NetworkXClient(tmp_path)
    client.build()
    callees_1 = {s.id for s in client.get_callees("a.py::a", depth=1)}
    callees_2 = {s.id for s in client.get_callees("a.py::a", depth=2)}
    assert callees_1 == {"b.py::b"}
    assert callees_2 == {"b.py::b", "c.py::c"}
    callers_1 = {s.id for s in client.get_callers("c.py::c", depth=1)}
    callers_2 = {s.id for s in client.get_callers("c.py::c", depth=2)}
    assert callers_1 == {"b.py::b"}
    assert callers_2 == {"b.py::b", "a.py::a"}

    impact_1 = client.get_impact_set(["c.py"], depth=1)
    impact_2 = client.get_impact_set(["c.py"], depth=2)
    assert impact_1.affected_files == ["b.py"]
    assert set(impact_2.affected_files) == {"a.py", "b.py"}


def test_unresolved_modules_are_not_invented() -> None:
    known = {"src/auth.py"}
    assert resolve_python_module("src/payments.py", "src.auth", 0, known) == "src/auth.py"
    assert resolve_python_module("src/auth.py", "typing", 0, known) is None
    assert resolve_ts_specifier("src/models.ts", "./auth", known) is None
    assert resolve_ts_specifier("src/models.ts", "./auth", {"src/auth.ts"}) == "src/auth.ts"
