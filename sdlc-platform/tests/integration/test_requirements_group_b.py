"""Group B against the Phase 03 benchmark corpus. Needs Postgres."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.helpers.hashing_adapter import HashingAdapter

from repo_intel.api import RepositoryIntelligence
from repo_intel.indexers.incremental import IncrementalIndexer
from requirements_engine.exceptions import SnapshotError
from requirements_engine.plans import EvidencePlan, PlanMethod
from requirements_engine.retrieve import RetrievalSession, execute_plan
from requirements_engine.snapshot import SnapshotCache, build_snapshot

CORPUS = Path(__file__).resolve().parents[1] / "benchmark" / "corpus"

pytestmark = pytest.mark.usefixtures("migrated_database_url")


def _copy_corpus(tmp_path: Path) -> Path:
    dest = tmp_path / "corpus"
    shutil.copytree(CORPUS, dest)
    (dest / "pyproject.toml").write_text(
        '[project]\nname = "corpus"\ndependencies = ["fastapi>=0.111"]\n',
        encoding="utf-8",
    )
    return dest


def _ri(session: AsyncSession, root: Path) -> RepositoryIntelligence:
    indexer = IncrementalIndexer(session, HashingAdapter(), root, enable_zoekt=False)
    return RepositoryIntelligence(session, HashingAdapter(), root, indexer=indexer)


async def test_snapshot_and_auth_retrieval_on_phase03_corpus(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    root = _copy_corpus(tmp_path)
    ri = _ri(db_session, root)
    await ri.index()

    cache = SnapshotCache()
    snapshot = await build_snapshot(ri, cache=cache)
    names = {service.name for service in snapshot.services}

    assert snapshot.index_state == "fresh"
    assert snapshot.languages == ["python"]
    assert "FastAPI" not in snapshot.languages
    assert names >= {"auth", "billing", "storage", "web", "shared"}
    assert snapshot.truncated is False or snapshot.other_service_count >= 0
    fastapi = [
        name
        for fact in snapshot.manifest_facts
        if fact.path == "pyproject.toml"
        for name in fact.names
    ]
    assert "fastapi" in fastapi

    reused = await build_snapshot(ri, cache=cache)
    assert reused is snapshot

    session = RetrievalSession(snapshot=snapshot)
    auth_plan = EvidencePlan(
        need="existing_auth_module",
        methods=[
            PlanMethod(signal="snapshot", query="auth", extractor="service_exists"),
            PlanMethod(
                signal="symbol",
                symbol_id="auth/service.py::AuthService",
                extractor="symbol_exists",
            ),
        ],
        accept_as="fact",
    )
    snapshot_hits = await execute_plan(auth_plan, snapshot, ri, session)
    assert any("auth" in ref.lower() for record in snapshot_hits for ref in record.refs)

    symbol_plan = EvidencePlan(
        need="does_AuthService_exist",
        methods=[
            PlanMethod(
                signal="symbol",
                symbol_id="auth/service.py::AuthService",
                extractor="symbol_exists",
            )
        ],
    )
    first = await execute_plan(symbol_plan, snapshot, ri, session)
    second = await execute_plan(symbol_plan, snapshot, ri, session)
    assert "auth/service.py::AuthService" in first[0].refs
    assert first[0].cache_hit is False
    assert second[0].cache_hit is True
    assert second[0].accept_as == "fact"

    semantic_plan = EvidencePlan(
        need="code_about_login",
        methods=[PlanMethod(signal="semantic", query="log a user in with email and password", top_k=3)],
        accept_as="inference",
    )
    semantic = await execute_plan(semantic_plan, snapshot, ri, session)
    assert semantic
    assert all(record.accept_as == "inference" for record in semantic)
    assert all(record.signal == "semantic" for record in semantic)

    lexical_plan = EvidencePlan(
        need="references_AuthService",
        methods=[PlanMethod(signal="lexical", query="AuthService")],
    )
    lexical = await execute_plan(lexical_plan, snapshot, ri, session)
    assert lexical[0].unavailable is True
    assert lexical[0].refs == []
    assert "Zoekt" in (lexical[0].unavailable_reason or "")


async def test_unindexed_corpus_fails_closed(db_session: AsyncSession, tmp_path: Path) -> None:
    root = _copy_corpus(tmp_path)
    ri = _ri(db_session, root)
    with pytest.raises(SnapshotError, match="unindexed"):
        await build_snapshot(ri, cache=SnapshotCache())


async def test_stale_corpus_fails_closed(db_session: AsyncSession, tmp_path: Path) -> None:
    root = _copy_corpus(tmp_path)
    ri = _ri(db_session, root)
    await ri.index()
    (root / "auth" / "service.py").write_text(
        (root / "auth" / "service.py").read_text(encoding="utf-8") + "\n# touched\n",
        encoding="utf-8",
    )
    with pytest.raises(SnapshotError, match="stale"):
        await build_snapshot(ri, cache=SnapshotCache())
