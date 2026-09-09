"""Group D integration: engine on the Phase 03 corpus. Needs Postgres."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.helpers.hashing_adapter import HashingAdapter
from tests.unit.test_engine import WELL_SPEC, _safe_context
from tests.unit.test_extract import RecordingAdapter

from repo_intel.api import RepositoryIntelligence
from repo_intel.indexers.incremental import IncrementalIndexer
from requirements_engine.engine import RequirementsEngine
from requirements_engine.snapshot import SnapshotCache

CORPUS = Path(__file__).resolve().parents[1] / "benchmark" / "corpus"

pytestmark = pytest.mark.usefixtures("migrated_database_url")


def _copy_corpus(tmp_path: Path) -> Path:
    dest = tmp_path / "corpus"
    shutil.copytree(CORPUS, dest)
    (dest / "pyproject.toml").write_text(
        '[project]\nname = "corpus"\ndependencies = ["fastapi>=0.111", "psycopg>=3"]\n',
        encoding="utf-8",
    )
    return dest


async def test_well_specified_corpus_session_is_spec_ready(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    root = _copy_corpus(tmp_path)
    indexer = IncrementalIndexer(db_session, HashingAdapter(), root, enable_zoekt=False)
    ri = RepositoryIntelligence(db_session, HashingAdapter(), root, indexer=indexer)
    await ri.index()

    engine = RequirementsEngine(
        "Add invoice CSV export for billing admins",
        RecordingAdapter(arguments=WELL_SPEC),
        ri,
        context=_safe_context(),
        snapshot_cache=SnapshotCache(),
    )
    result = await engine.run()
    assert result.action == "spec_ready"
    assert result.counters.llm_calls == 1
    assert result.counters.human_questions == 0
    assert result.spec is not None
    assert result.spec["functional"]
    auto_text = " ".join(item.answer for item in result.auto_answers).lower()
    assert "python" in auto_text
