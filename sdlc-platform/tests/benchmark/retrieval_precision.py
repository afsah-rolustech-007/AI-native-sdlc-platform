"""Section 06 retrieval benchmark: success@5 over frozen labeled queries.

Run it:
    uv run python tests/benchmark/retrieval_precision.py            # needs Postgres
    uv run pytest tests/benchmark -m benchmark                      # same, as a test

Metric — success@5: a query counts as a hit when at least one gold answer appears
in the first 5 results. We report this rather than classic precision@5 because
most queries here have exactly one correct answer, so precision@5 is capped at
0.20 and would measure nothing. Success@5 answers the question that matters for
an agent: "did the right code make it into the context window?"

Each of the four signals is scored separately and never fused. A miss is
attributable to semantic, lexical, or graph retrieval — not to a ranking formula.

Labels live in `queries.json` and the corpus in `corpus/`. Both are frozen: fix
retrieval when a query fails, do not relabel it.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config import get_settings
from common.db import make_async_engine, make_session_factory
from repo_intel.api import RepositoryIntelligence
from repo_intel.exceptions import RepoIntelError, ZoektNotIndexedError, ZoektUnavailableError
from tests.helpers.hashing_adapter import HashingAdapter

BENCH_DIR = Path(__file__).resolve().parent
QUERIES_PATH = BENCH_DIR / "queries.json"
CORPUS = BENCH_DIR / "corpus"
TOP_K = 5

# Phase 03's numeric completion criterion.
TARGET = 0.90


@dataclass
class QueryResult:
    query_id: str
    query_type: str
    signal: str
    hit: bool
    skipped: bool = False
    returned: list[str] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    results: list[QueryResult]

    @property
    def scored(self) -> list[QueryResult]:
        return [item for item in self.results if not item.skipped]

    @property
    def overall(self) -> float:
        scored = self.scored
        return sum(item.hit for item in scored) / len(scored) if scored else 0.0

    def _rate(self, key: str) -> dict[str, tuple[int, int]]:
        buckets: dict[str, list[QueryResult]] = defaultdict(list)
        for item in self.scored:
            buckets[getattr(item, key)].append(item)
        return {
            name: (sum(i.hit for i in items), len(items)) for name, items in sorted(buckets.items())
        }

    def by_signal(self) -> dict[str, tuple[int, int]]:
        return self._rate("signal")

    def by_type(self) -> dict[str, tuple[int, int]]:
        return self._rate("query_type")

    def misses(self) -> list[QueryResult]:
        return [item for item in self.scored if not item.hit]


def load_queries() -> list[dict]:
    payload = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    return list(payload["queries"])


async def _run_query(ri: RepositoryIntelligence, spec: dict) -> QueryResult:
    """Route one labeled query to its single signal and truncate to top-5."""
    kind = spec["type"]
    gold = set(spec["gold"])
    returned: list[str]

    if kind == "find_by_concept":
        hits = await ri.search_concepts(spec["query"], TOP_K)
        returned = [hit.symbol_id or hit.file_path for hit in hits]
    elif kind == "find_similar_implementation":
        hits = await ri.find_similar_implementations(spec["query"], TOP_K)
        returned = [hit.symbol_id or hit.file_path for hit in hits]
    elif kind == "find_caller":
        returned = [symbol.id for symbol in await ri.get_callers(spec["target"])][:TOP_K]
    elif kind == "find_dependents":
        returned = (await ri.get_dependents(spec["target"]))[:TOP_K]
    elif kind == "find_symbol":
        try:
            lexical = await ri.search_codebase(spec["query"], TOP_K)
        except (ZoektUnavailableError, ZoektNotIndexedError) as exc:
            print(f"  {spec['id']}: skipped (zoekt unavailable: {exc})")
            return QueryResult(spec["id"], kind, spec["signal"], hit=False, skipped=True)
        # Zoekt returns line hits; collapse to files before scoring.
        returned = list(dict.fromkeys(hit.file_path for hit in lexical))[:TOP_K]
    else:
        raise ValueError(f"unknown query type in queries.json: {kind}")

    return QueryResult(
        query_id=spec["id"],
        query_type=kind,
        signal=spec["signal"],
        hit=bool(gold & set(returned)),
        returned=returned,
    )


async def run_benchmark(ri: RepositoryIntelligence) -> BenchmarkReport:
    """Index the frozen corpus through the public API, then score every query."""
    stats = await ri.index()
    status = await ri.index_status()
    print(
        f"corpus {status.state}: {status.file_count} files "
        f"({stats.files_parsed} parsed this run, {stats.chunks_embedded} chunks embedded, "
        f"{stats.unchanged} files already current)"
    )
    results = [await _run_query(ri, spec) for spec in load_queries()]
    return BenchmarkReport(results)


def print_report(report: BenchmarkReport) -> None:
    print("\nsuccess@5 by signal")
    for name, (hits, total) in report.by_signal().items():
        print(f"  {name:<9} {hits}/{total}  {hits / total:.0%}")
    print("\nsuccess@5 by query type")
    for name, (hits, total) in report.by_type().items():
        print(f"  {name:<28} {hits}/{total}  {hits / total:.0%}")

    misses = report.misses()
    if misses:
        print("\nmisses")
        for item in misses:
            print(f"  {item.query_id} ({item.query_type}) returned: {item.returned}")

    skipped = [item for item in report.results if item.skipped]
    if skipped:
        print(f"\nskipped (signal unavailable): {[i.query_id for i in skipped]}")

    verdict = "PASS" if report.overall >= TARGET else "BELOW TARGET"
    print(f"\noverall success@5 = {report.overall:.1%} (target {TARGET:.0%}) — {verdict}")


async def _main() -> int:
    engine = make_async_engine(get_settings().database_url)
    factory = make_session_factory(engine)
    try:
        async with factory() as session:
            ri = RepositoryIntelligence(session, HashingAdapter(), CORPUS)
            report = await run_benchmark(ri)
    except RepoIntelError as exc:
        print(f"benchmark could not run: {exc}")
        print("Postgres with migrations is required: make up && make migrate")
        return 2
    finally:
        await engine.dispose()
    print_report(report)
    return 0 if report.overall >= TARGET else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
