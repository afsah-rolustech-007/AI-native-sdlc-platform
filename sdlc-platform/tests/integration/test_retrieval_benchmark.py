"""Runs the Section 06 success@5 benchmark as part of the suite.

The corpus and labels are frozen, so this doubles as a regression guard: a
chunking or ranking change that drops retrieval quality fails here.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.benchmark.retrieval_precision import (
    CORPUS,
    TARGET,
    BenchmarkReport,
    load_queries,
    print_report,
    run_benchmark,
)
from tests.helpers.hashing_adapter import HashingAdapter

from repo_intel.api import RepositoryIntelligence
from repo_intel.indexers.incremental import IncrementalIndexer

pytestmark = [pytest.mark.usefixtures("migrated_database_url"), pytest.mark.benchmark]


def test_every_labeled_query_has_a_known_type_and_gold_answer() -> None:
    known = {
        "find_by_concept",
        "find_similar_implementation",
        "find_caller",
        "find_dependents",
        "find_symbol",
    }
    queries = load_queries()

    assert len(queries) >= 20  # §6 asks for ~20-30 labeled queries
    assert {spec["id"] for spec in queries}.__len__() == len(queries)
    for spec in queries:
        assert spec["type"] in known, spec
        assert spec["gold"], spec


async def test_success_at_5_meets_the_phase_03_target(db_session: AsyncSession) -> None:
    indexer = IncrementalIndexer(db_session, HashingAdapter(), CORPUS, enable_zoekt=False)
    ri = RepositoryIntelligence(db_session, HashingAdapter(), CORPUS, indexer=indexer)

    report: BenchmarkReport = await run_benchmark(ri)
    print_report(report)

    assert report.scored, "no queries were scored — every signal was unavailable"
    assert report.overall >= TARGET, f"success@5 {report.overall:.1%} < target {TARGET:.0%}"
