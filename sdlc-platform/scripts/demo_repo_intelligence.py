"""Phase 03 demo: incremental re-index of an uncommitted edit + the Section 06 API.

  uv run python scripts/demo_repo_intelligence.py

Shows, in order:
  1. full index of the benchmark corpus through RepositoryIntelligence
  2. index_status() == fresh
  3. an UNCOMMITTED working-tree edit -> status goes stale -> reindex timing
     (only the edited file is parsed; unchanged chunks are not re-embedded)
  4. StaleIndexError fail-closed behaviour
  5. get_architecture_summary() and get_aider_repo_map()

Deterministic hashing embedder, so no GLM_API_KEY needed.
Requires Postgres with migrations: make up && make migrate
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.helpers.hashing_adapter import HashingAdapter

from common.config import get_settings
from common.db import make_async_engine, make_session_factory
from repo_intel.api import RepositoryIntelligence
from repo_intel.exceptions import RepoIntelError, StaleIndexError

CORPUS = ROOT / "tests" / "benchmark" / "corpus"
EDIT_TARGET = CORPUS / "shared" / "validation.py"
EDIT = '''

def validate_postcode(code: str) -> bool:
    """Return True for a five-digit postal code."""
    return len(code) == 5 and code.isdigit()
'''


async def _demo(ri: RepositoryIntelligence) -> None:
    started = time.perf_counter()
    stats = await ri.index()
    print(
        f"1. index(): {stats.files_parsed} files parsed, {stats.symbols_indexed} symbols, "
        f"{stats.chunks_embedded} chunks embedded in {time.perf_counter() - started:.2f}s"
    )

    status = await ri.index_status()
    print(f"2. index_status(): {status.state} ({status.file_count} files)")

    original = EDIT_TARGET.read_text(encoding="utf-8")
    try:
        EDIT_TARGET.write_text(original + EDIT, encoding="utf-8")
        stale = await ri.index_status()
        print(f"3. after an uncommitted edit: {stale.state}, stale_paths={stale.stale_paths}")

        try:
            await ri.search_concepts("validate a postal code", 3)
        except StaleIndexError as exc:
            print(f"4. reads fail closed: StaleIndexError({exc})")

        started = time.perf_counter()
        delta = await ri.reindex()
        print(
            f"5. reindex(): {delta.modified} modified, {delta.unchanged} unchanged files, "
            f"{delta.chunks_embedded} chunks embedded, "
            f"{delta.chunks_skipped_unchanged} chunks reused, in {delta.elapsed_s:.2f}s "
            f"(wall {time.perf_counter() - started:.2f}s)"
        )

        hits = await ri.search_concepts("validate a postal code", 3)
        for hit in hits:
            score = f"{hit.score:.3f}" if hit.score is not None else "?"
            print(f"     {hit.symbol_id}  kind={hit.kind}  score={score}")
    finally:
        EDIT_TARGET.write_text(original, encoding="utf-8")
        await ri.reindex()

    callers = await ri.get_callers("shared/validation.py::validate_amount")
    print(f"6. get_callers(validate_amount): {[symbol.id for symbol in callers]}")

    print(f"7. get_aider_repo_map(top_n=5): {await ri.get_aider_repo_map(top_n=5)}")

    summary = json.loads(await ri.get_architecture_summary())
    print("8. get_architecture_summary():")
    print(f"     services: {summary['services']}")
    print(f"     shared_modules: {summary['shared_modules']}")
    print(f"     database_entities: {summary['database_entities']}")
    print(f"     api_boundaries: {summary['api_boundaries']}")


async def _run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    engine = make_async_engine(get_settings().database_url)
    factory = make_session_factory(engine)
    try:
        async with factory() as session:
            await _demo(RepositoryIntelligence(session, HashingAdapter(), CORPUS))
    except RepoIntelError as exc:
        print(f"\ndemo failed: {exc}")
        print("Postgres with migrations is required: make up && make migrate")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_run())
