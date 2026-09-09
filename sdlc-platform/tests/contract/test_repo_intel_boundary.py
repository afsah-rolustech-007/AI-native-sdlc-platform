"""§G.1 / Section 06 acceptance: RepositoryIntelligence is the only door in.

From Phase 04 onward, application code must not reach past the API into the
symbol store, Zoekt, NetworkX, or pgvector. This is the grep-verifiable check
the section's acceptance criteria call for. Same pattern as Phase 02's
provider-SDK guard.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Modules an agent must never import directly.
FORBIDDEN_MODULES = (
    "repo_intel.symbol_store",
    "repo_intel.indexers.zoekt_client",
    "repo_intel.indexers.treesitter",
    "repo_intel.indexers.incremental",
    "repo_intel.graph",
    "repo_intel.vector",
)

# Where agent/application code lives today. `packages/repo_intel` itself is the
# implementation and is obviously allowed to import its own internals.
CALLER_TREES = (
    "apps",
    "packages/orchestration",
    "packages/common",
    "packages/requirements_engine",
)

# Indexing entry points and demos legitimately drive the clients directly.
ALLOWLIST = {
    "scripts/demo_dependency_graph.py",
    "scripts/demo_lexical_search.py",
    "scripts/demo_section01.py",
    "scripts/demo_section02.py",
    "scripts/demo_section03.py",
    "scripts/demo_section04.py",
    "scripts/demo_semantic_search.py",
    "scripts/demo_symbol_index.py",
    "scripts/ri_index.py",
}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _violations(directory: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(directory.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        if relative in ALLOWLIST:
            continue
        for module in _imported_modules(path):
            if any(module == bad or module.startswith(bad + ".") for bad in FORBIDDEN_MODULES):
                found.append((relative, module))
    return found


def test_application_code_only_talks_to_repository_intelligence() -> None:
    violations: list[tuple[str, str]] = []
    for tree in CALLER_TREES:
        directory = ROOT / tree
        if directory.is_dir():
            violations.extend(_violations(directory))

    assert not violations, (
        "import RepositoryIntelligence instead of a Section 01-05 client: " f"{violations}"
    )


def test_scripts_outside_the_allowlist_use_the_api() -> None:
    """New scripts must go through the API; add to ALLOWLIST only for indexing/demos."""
    assert not _violations(ROOT / "scripts")


def test_repository_intelligence_exposes_all_four_signals() -> None:
    from repo_intel.api import RepositoryIntelligence

    for method in (
        "get_symbol_signature",  # symbol
        "search_codebase",  # lexical
        "search_concepts",  # semantic
        "get_impact_set",  # graph
        "index",
        "reindex",
        "reindex_paths",
        "index_status",
        "get_architecture_summary",
        "get_aider_repo_map",
    ):
        assert callable(getattr(RepositoryIntelligence, method)), method
