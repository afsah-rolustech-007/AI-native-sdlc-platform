"""Phase 04 Group B checkpoint: snapshot + EvidencePlan + targeted RI.

  uv run python scripts/demo_requirements_group_b.py

Uses the Phase 03 benchmark corpus. Deterministic hashing embedder, so no
GLM_API_KEY is required. Needs Postgres: make up && make migrate

Prints:
  1. bounded snapshot
  2. auth EvidencePlan + targeted retrieval (auth/service.py)
  3. the same query again (cache hit)
  4. semantic evidence recorded as inference, not FACT
  5. Zoekt unavailable fail-closed (not zero hits)
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.helpers.hashing_adapter import HashingAdapter

from common.config import get_settings
from common.db import make_async_engine, make_session_factory
from repo_intel.api import RepositoryIntelligence
from requirements_engine.plans import EvidencePlan, PlanMethod
from requirements_engine.retrieve import RetrievalSession, execute_plan
from requirements_engine.snapshot import SnapshotCache, build_snapshot

CORPUS = ROOT / "tests" / "benchmark" / "corpus"


def _print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_records(records) -> None:
    for record in records:
        print(
            f"  {record.id} signal={record.signal} method={record.ri_method} "
            f"accept_as={record.accept_as} cache_hit={record.cache_hit} "
            f"unavailable={record.unavailable} refs={record.refs[:6]}"
        )
        if record.excerpt:
            print(f"    excerpt: {record.excerpt[:120]}")
        if record.unavailable_reason:
            print(f"    error: {record.unavailable_reason}")


def _print_traces(session: RetrievalSession) -> None:
    print("traces:")
    for trace in session.traces:
        print(
            f"  signal={trace.signal} ri={trace.ri_method} query={trace.query!r} "
            f"cache_hit={trace.cache_hit} results={trace.result_count} "
            f"budget_used={trace.budget_used} unavailable={trace.unavailable} "
            f"error={trace.error}"
        )
    print(
        f"budget: ri_calls={session.ri_calls} remaining={session.remaining_budget} "
        f"zoekt={session.zoekt} embeddings={session.embeddings}"
    )


async def _demo() -> None:
    settings = get_settings()
    engine = make_async_engine(settings.database_url)
    factory = make_session_factory(engine)
    tmp = Path(tempfile.mkdtemp(prefix="sdlc-group-b-"))
    root = tmp / "corpus"
    try:
        shutil.copytree(CORPUS, root)
        (root / "pyproject.toml").write_text(
            '[project]\nname = "corpus"\ndependencies = ["fastapi>=0.111"]\n',
            encoding="utf-8",
        )
        async with factory() as session:
            ri = RepositoryIntelligence(session, HashingAdapter(), root)
            # Demo step 5 needs lexical to fail closed. Skip Zoekt so missing
            # binaries are not confused with "zero hits".
            ri._indexer.enable_zoekt = False
            stats = await ri.index()
            print(
                f"indexed {stats.files_parsed} files, {stats.symbols_indexed} symbols, "
                f"{stats.chunks_embedded} chunks"
            )

            cache = SnapshotCache()
            snapshot = await build_snapshot(ri, cache=cache)
            _print_header("1. SessionRepoSnapshot")
            print(
                json.dumps(
                    {
                        "repo_root": snapshot.repo_root,
                        "catalog_hash": snapshot.catalog_hash,
                        "file_count": snapshot.file_count,
                        "languages": snapshot.languages,
                        "services": [service.name for service in snapshot.services],
                        "other_service_count": snapshot.other_service_count,
                        "api_boundaries": snapshot.api_boundaries,
                        "database_entities": snapshot.database_entities,
                        "shared_modules": snapshot.shared_modules,
                        "top_files": snapshot.top_files,
                        "manifest_facts": [fact.model_dump() for fact in snapshot.manifest_facts],
                        "capabilities": snapshot.capabilities.model_dump(),
                        "truncated": snapshot.truncated,
                        "token_estimate": snapshot.token_estimate,
                    },
                    indent=2,
                )
            )
            again = await build_snapshot(ri, cache=cache)
            print(f"snapshot cache: hits={cache.hits} misses={cache.misses} same_object={again is snapshot}")

            retrieval = RetrievalSession(snapshot=snapshot, task_id="group-b-demo")
            auth_plan = EvidencePlan(
                need="existing_auth_module",
                methods=[
                    PlanMethod(signal="snapshot", query="auth", extractor="service_exists"),
                    PlanMethod(
                        signal="symbol",
                        symbol_id="auth/service.py::AuthService",
                        extractor="symbol_exists",
                    ),
                    PlanMethod(signal="lexical", query="AuthService"),
                ],
                accept_as="fact",
                max_ri_calls=4,
            )
            _print_header("2. Auth EvidencePlan (snapshot first)")
            print(auth_plan.model_dump_json(indent=2))
            snapshot_records = await execute_plan(auth_plan, snapshot, ri, retrieval)
            print("chosen methods: snapshot (stops if auth service is visible)")
            _print_records(snapshot_records)

            symbol_plan = EvidencePlan(
                need="does_AuthService_exist",
                methods=[
                    PlanMethod(
                        signal="symbol",
                        symbol_id="auth/service.py::AuthService",
                        extractor="symbol_exists",
                    )
                ],
                accept_as="fact",
            )
            _print_header("2b. Targeted symbol retrieval")
            print(f"method chosen: {symbol_plan.methods[0].signal} → get_symbol_signature")
            first = await execute_plan(symbol_plan, snapshot, ri, retrieval)
            _print_records(first)

            _print_header("3. Repeat the same symbol query")
            second = await execute_plan(symbol_plan, snapshot, ri, retrieval)
            _print_records(second)
            print(f"cache hit: {second[0].cache_hit}")

            semantic_plan = EvidencePlan(
                need="code_about_login",
                methods=[
                    PlanMethod(
                        signal="semantic",
                        query="log a user in with their email and password",
                        top_k=3,
                    )
                ],
                accept_as="inference",
            )
            _print_header("4. Semantic evidence (NOT FACT)")
            semantic = await execute_plan(semantic_plan, snapshot, ri, retrieval)
            _print_records(semantic)
            print(f"all accept_as inference: {all(item.accept_as == 'inference' for item in semantic)}")

            lexical_plan = EvidencePlan(
                need="references_AuthService",
                methods=[PlanMethod(signal="lexical", query="AuthService")],
            )
            _print_header("5. Zoekt unavailable (fail closed, not zero hits)")
            lexical = await execute_plan(lexical_plan, snapshot, ri, retrieval)
            _print_records(lexical)

            _print_header("Session retrieval traces")
            _print_traces(retrieval)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        await engine.dispose()


def main() -> None:
    asyncio.run(_demo())


if __name__ == "__main__":
    main()
