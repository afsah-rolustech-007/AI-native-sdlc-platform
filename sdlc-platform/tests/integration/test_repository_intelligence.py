"""Section 06: RepositoryIntelligence is the single door, and it fails closed."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.helpers.hashing_adapter import HashingAdapter

from repo_intel.api import RepositoryIntelligence
from repo_intel.exceptions import FileNotIndexedError, StaleIndexError, SymbolNotFoundError
from repo_intel.indexers.incremental import IncrementalIndexer

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "source_tree"
AUTH = "src/auth.py"
VALIDATE = "src/auth.py::validate_token"
CHARGE = "src/payments.py::ChargeService.charge"

pytestmark = pytest.mark.usefixtures("migrated_database_url")


def _tree(tmp_path: Path) -> Path:
    dest = tmp_path / "tree"
    shutil.copytree(FIXTURE, dest)
    return dest


def _ri(session: AsyncSession, root: Path) -> RepositoryIntelligence:
    indexer = IncrementalIndexer(session, HashingAdapter(), root, enable_zoekt=False)
    return RepositoryIntelligence(session, HashingAdapter(), root, indexer=indexer)


async def _indexed(session: AsyncSession, tmp_path: Path) -> tuple[RepositoryIntelligence, Path]:
    root = _tree(tmp_path)
    ri = _ri(session, root)
    await ri.index()
    return ri, root


async def test_structural_reads_return_working_tree_truth(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    ri, _ = await _indexed(db_session, tmp_path)

    assert "validate_token" in await ri.get_symbol_signature(VALIDATE)
    body = await ri.get_symbol_body(VALIDATE)
    assert body.startswith("def validate_token")
    assert "token.strip()" in body
    structure = await ri.get_file_structure(AUTH)
    assert VALIDATE in {symbol.id for symbol in structure}


async def test_graph_reads_hydrate_a_cold_in_memory_graph(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """NetworkX is RAM-only; a fresh process must rebuild it instead of erroring."""
    ri, _ = await _indexed(db_session, tmp_path)
    assert ri._indexer.graph.is_built is False

    callers = await ri.get_callers(VALIDATE)

    assert CHARGE in {symbol.id for symbol in callers}
    assert await ri.get_dependents(AUTH) == ["src/payments.py"]
    impact = await ri.get_impact_set([AUTH])
    assert "src/payments.py" in impact.affected_files


async def test_semantic_search_returns_metadata_for_section_06_filtering(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    ri, _ = await _indexed(db_session, tmp_path)

    hits = await ri.search_concepts("function that validates user input", 5)

    assert VALIDATE in {hit.symbol_id for hit in hits}
    assert all(hit.kind and hit.chunk_tokens > 0 for hit in hits)
    kinds_only = await ri.search_concepts("validate", 5, kinds=["class"])
    assert {hit.kind for hit in kinds_only} <= {"class"}


async def test_every_read_fails_closed_when_the_tree_drifts(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    ri, root = await _indexed(db_session, tmp_path)
    (root / AUTH).write_text("# gutted\n", encoding="utf-8")

    for call in (
        ri.get_symbol_signature(VALIDATE),
        ri.get_symbol_body(VALIDATE),
        ri.get_file_structure(AUTH),
        ri.get_callers(VALIDATE),
        ri.get_dependents(AUTH),
        ri.search_concepts("validate", 3),
        ri.find_similar_implementations("def f(): pass", 3),
        ri.get_architecture_summary(),
        ri.get_aider_repo_map(),
    ):
        with pytest.raises(StaleIndexError):
            await call


async def test_refresh_true_reindexes_instead_of_raising(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    ri, root = await _indexed(db_session, tmp_path)
    (root / AUTH).write_text(
        'def brand_new_helper(x):\n    """Double a number."""\n    return x * 2\n',
        encoding="utf-8",
    )

    structure = await ri.get_file_structure(AUTH, refresh=True)

    functions = {symbol.name for symbol in structure if symbol.kind == "function"}
    assert functions == {"brand_new_helper"}
    assert (await ri.index_status()).state == "fresh"


async def test_unknown_symbol_and_file_raise_instead_of_returning_empty(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    ri, _ = await _indexed(db_session, tmp_path)

    with pytest.raises(SymbolNotFoundError):
        await ri.get_symbol_signature("src/auth.py::nope")
    with pytest.raises(FileNotIndexedError):
        await ri.get_file_structure("src/does_not_exist.py")


async def test_architecture_summary_is_ast_derived_json(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    ri, root = await _indexed(db_session, tmp_path)

    summary = json.loads(await ri.get_architecture_summary())

    assert summary["generated_by"] == "ast"
    assert summary["repo_root"] == str(root)
    assert "src" in summary["services"]
    assert summary["symbol_count"] > 0
    assert await ri.get_aider_repo_map(top_n=3)


async def test_deferred_methods_fail_loudly_instead_of_faking_results(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    ri, _ = await _indexed(db_session, tmp_path)

    with pytest.raises(NotImplementedError, match="Phase 12"):
        await ri.find_relevant_context("anything")
    with pytest.raises(NotImplementedError, match="Phase 06"):
        await ri.get_regression_history(VALIDATE)
    with pytest.raises(NotImplementedError, match="Phase 06"):
        await ri.get_design_decisions(VALIDATE)
    with pytest.raises(NotImplementedError, match="Phase 06"):
        await ri.get_change_frequency(AUTH)
