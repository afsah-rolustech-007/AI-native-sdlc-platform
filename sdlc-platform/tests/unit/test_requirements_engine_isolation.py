"""Group B may import the RI public door, not internals or LangGraph."""

from __future__ import annotations

import ast
from pathlib import Path

from repo_intel.api import RepositoryIntelligence

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "packages" / "requirements_engine"

_FORBIDDEN = ("langgraph", "orchestration")
_ALLOWED_RI = (
    "repo_intel.api",
    "repo_intel.exceptions",
    "repo_intel.models",
)
_FORBIDDEN_RI_INTERNALS = (
    "repo_intel.symbol_store",
    "repo_intel.indexers",
    "repo_intel.graph",
    "repo_intel.vector",
    "repo_intel.summary",
    "repo_intel.tables",
)

# Phase 03 public surface. Group B must not add methods here.
_FROZEN_RI_PUBLIC = {
    "index",
    "reindex",
    "reindex_paths",
    "index_status",
    "get_symbol_signature",
    "get_symbol_body",
    "get_file_structure",
    "get_callers",
    "get_callees",
    "get_dependencies",
    "get_dependents",
    "get_impact_set",
    "search_concepts",
    "find_similar_implementations",
    "search_codebase",
    "get_architecture_summary",
    "get_aider_repo_map",
    "find_relevant_context",
    "get_regression_history",
    "get_design_decisions",
    "get_change_frequency",
}

# Methods the engine is allowed to *call*. find_relevant_context is not on this list.
_ALLOWED_RI_CALLS = {
    "index_status",
    "get_architecture_summary",
    "get_aider_repo_map",
    "get_symbol_signature",
    "get_file_structure",
    "search_codebase",
    "search_concepts",
    "get_callers",
    "get_callees",
    "get_dependencies",
    "get_dependents",
    "get_impact_set",
    "repo_root",
}


def _imported(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _trees() -> list[ast.AST]:
    return [
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in sorted(ENGINE.rglob("*.py"))
    ]


def test_requirements_engine_does_not_import_langgraph_or_ri_internals() -> None:
    offenders: list[str] = []
    for path in sorted(ENGINE.rglob("*.py")):
        for module in _imported(path):
            if any(module == bad or module.startswith(bad + ".") for bad in _FORBIDDEN):
                offenders.append(f"{path.relative_to(ROOT)}:{module}")
            if module == "repo_intel" or module.startswith("repo_intel."):
                allowed = any(
                    module == ok or module.startswith(ok + ".") for ok in _ALLOWED_RI
                )
                internal = any(
                    module == bad or module.startswith(bad + ".")
                    for bad in _FORBIDDEN_RI_INTERNALS
                )
                if internal or not allowed:
                    offenders.append(f"{path.relative_to(ROOT)}:{module}")
    assert offenders == []


def test_engine_never_calls_find_relevant_context_or_refresh_true() -> None:
    problems: list[str] = []
    for path in sorted(ENGINE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "find_relevant_context":
                problems.append(f"{path.name}:{node.lineno}:find_relevant_context")
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if (
                        keyword.arg == "refresh"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                    ):
                        problems.append(f"{path.name}:{node.lineno}:refresh=True")
    assert problems == []


def test_engine_only_calls_existing_ri_methods() -> None:
    unknown: list[str] = []
    for path in sorted(ENGINE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _FROZEN_RI_PUBLIC
                and node.func.attr not in _ALLOWED_RI_CALLS
            ):
                unknown.append(f"{path.name}:{node.lineno}:{node.func.attr}")
    assert unknown == []


def test_decision_layer_does_not_import_llm_or_ri() -> None:
    """Group C must not call a model or Repository Intelligence."""
    forbidden = ("langgraph", "orchestration", "model_adapters", "repo_intel")
    names = {
        "classify.py",
        "auto_answer.py",
        "rank.py",
        "render.py",
        "decide.py",
        "extractors.py",
        "sufficiency.py",
        "trace.py",
        "seed.py",
    }
    offenders: list[str] = []
    for path in sorted(ENGINE.rglob("*.py")):
        if path.name not in names:
            continue
        for module in _imported(path):
            if any(module == bad or module.startswith(bad + ".") for bad in forbidden):
                offenders.append(f"{path.name}:{module}")
            if module == "requirements_engine.extract" or module.startswith(
                "requirements_engine.extract."
            ):
                offenders.append(f"{path.name}:{module}")
            if module == "requirements_engine.retrieve" or module.startswith(
                "requirements_engine.retrieve."
            ):
                offenders.append(f"{path.name}:{module}")
    assert offenders == []


def test_no_new_ri_public_methods() -> None:
    public = {
        name
        for name, value in RepositoryIntelligence.__dict__.items()
        if not name.startswith("_") and callable(value)
    }
    assert public == _FROZEN_RI_PUBLIC


def test_group_d_does_not_import_langgraph_or_interrupt() -> None:
    forbidden = ("langgraph", "orchestration")
    names = {"engine.py", "sufficiency.py", "trace.py", "seed.py"}
    offenders: list[str] = []
    for path in sorted(ENGINE.rglob("*.py")):
        if path.name not in names:
            continue
        text = path.read_text(encoding="utf-8")
        if "interrupt(" in text:
            offenders.append(f"{path.name}:interrupt(")
        if "compute_confidence(" in text:
            offenders.append(f"{path.name}:compute_confidence(")
        for module in _imported(path):
            if any(module == bad or module.startswith(bad + ".") for bad in forbidden):
                offenders.append(f"{path.name}:{module}")
    assert offenders == []
