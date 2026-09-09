"""Section 06 §G.7: the summary is derived from symbols + import edges, never an LLM."""

from __future__ import annotations

from repo_intel.models import Symbol
from repo_intel.summary import build_architecture_summary, rank_files_by_in_degree, service_of


def _symbol(symbol_id: str, kind: str = "function") -> Symbol:
    path, _, name = symbol_id.partition("::")
    return Symbol(id=symbol_id, kind=kind, name=name, file_path=path, start_line=1, end_line=2)


ADJACENCY = {
    "web/main.py": ["auth/service.py", "shared/config.py"],
    "auth/service.py": ["shared/config.py"],
    "shared/config.py": [],
    "storage/models.py": [],
}
SYMBOLS = [
    _symbol("web/main.py::main"),
    _symbol("auth/service.py::AuthService", kind="class"),
    _symbol("shared/config.py::load_settings"),
    _symbol("storage/models.py::User", kind="class"),
]


def test_service_is_the_first_path_segment() -> None:
    assert service_of("auth/service.py") == "auth"
    assert service_of("main.py") == "<root>"


def test_summary_groups_by_service_and_finds_cross_service_edges() -> None:
    summary = build_architecture_summary("/repo", SYMBOLS, ADJACENCY)

    assert summary["services"] == ["auth", "shared", "storage", "web"]
    assert summary["service_map"]["web"]["dependencies"] == ["auth", "shared"]
    assert {"from": "web/main.py", "to": "shared/config.py"} in summary["cross_service_dependencies"]


def test_entry_points_shared_modules_and_db_entities_are_detected() -> None:
    summary = build_architecture_summary("/repo", SYMBOLS, ADJACENCY)

    assert summary["service_map"]["web"]["entry_points"] == ["web/main.py"]
    # config.py is imported from two different services, so it is shared.
    assert summary["shared_modules"] == ["shared/config.py"]
    assert summary["database_entities"] == ["storage/models.py::User"]


def test_summary_is_deterministic_for_the_same_input() -> None:
    assert build_architecture_summary("/repo", SYMBOLS, ADJACENCY) == build_architecture_summary(
        "/repo", SYMBOLS, ADJACENCY
    )


def test_repo_map_ranks_by_in_degree_then_path() -> None:
    ranked = rank_files_by_in_degree(ADJACENCY)

    assert ranked[0] == ("shared/config.py", 2)
    assert ("storage/models.py", 0) in ranked
