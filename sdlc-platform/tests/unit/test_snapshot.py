"""Group B: SessionRepoSnapshot from Phase 03 RI metadata only."""

from __future__ import annotations

import pytest
from tests.helpers.fake_repo_intel import FakeRI

from requirements_engine.exceptions import SnapshotError
from requirements_engine.snapshot import (
    MAX_ENTRY_POINTS,
    MAX_KEY_SYMBOLS,
    MAX_SERVICES,
    SnapshotCache,
    build_snapshot,
)


async def test_snapshot_creation_is_capped_and_has_no_file_bodies() -> None:
    ri = FakeRI()
    cache = SnapshotCache()
    snapshot = await build_snapshot(ri, cache=cache)

    assert snapshot.index_state == "fresh"
    assert snapshot.catalog_hash == "hash1"
    assert snapshot.file_count == 12
    assert snapshot.languages == ["python"]
    assert "FastAPI" not in snapshot.languages
    assert {service.name for service in snapshot.services} >= {"auth", "billing", "storage", "web"}
    auth = next(service for service in snapshot.services if service.name == "auth")
    assert "auth/service.py::AuthService" in auth.key_symbols
    dumped = snapshot.model_dump()
    assert "cross_service_dependencies" not in dumped
    assert "class AuthService" not in str(dumped)
    assert snapshot.token_estimate > 0
    assert snapshot.capabilities.graph == "available"
    assert ri.call_count("get_architecture_summary") == 1
    assert ri.call_count("get_aider_repo_map") == 1
    assert ri.refresh_true_calls() == []


async def test_snapshot_size_caps_bind_on_large_service_maps() -> None:
    service_map = {
        f"svc{index:02d}": {
            "files": 10,
            "entry_points": [f"svc{index:02d}/e{n}.py" for n in range(12)],
            "key_symbols": [f"svc{index:02d}/mod.py::S{n}" for n in range(12)],
            "dependencies": ["shared"],
            "tech_stack": ["python"],
        }
        for index in range(50)
    }
    ri = FakeRI(
        summary={
            "service_map": service_map,
            "api_boundaries": [f"api/{n}.py" for n in range(40)],
            "database_entities": [f"db.py::E{n}" for n in range(40)],
            "shared_modules": [f"shared/{n}.py" for n in range(40)],
        }
    )
    snapshot = await build_snapshot(ri, cache=SnapshotCache())

    assert len(snapshot.services) == MAX_SERVICES
    assert snapshot.other_service_count == 10
    assert snapshot.truncated is True
    for service in snapshot.services:
        assert len(service.entry_points) <= MAX_ENTRY_POINTS
        assert len(service.key_symbols) <= MAX_KEY_SYMBOLS
    assert len(snapshot.api_boundaries) == 20
    assert len(snapshot.database_entities) == 20
    assert len(snapshot.shared_modules) == 20


async def test_snapshot_cache_hit_skips_summary_and_map() -> None:
    ri = FakeRI()
    cache = SnapshotCache()
    first = await build_snapshot(ri, cache=cache)
    second = await build_snapshot(ri, cache=cache)

    assert first is second
    assert cache.hits == 1
    assert cache.misses == 1
    assert ri.call_count("get_architecture_summary") == 1
    assert ri.call_count("get_aider_repo_map") == 1


async def test_snapshot_cache_invalidates_when_catalog_hash_changes() -> None:
    ri = FakeRI(catalog_hash="aaa")
    cache = SnapshotCache()
    first = await build_snapshot(ri, cache=cache)
    ri.catalog_hash = "bbb"
    second = await build_snapshot(ri, cache=cache)

    assert first.catalog_hash == "aaa"
    assert second.catalog_hash == "bbb"
    assert ri.call_count("get_architecture_summary") == 2
    assert cache.get(first.repo_root, "aaa") is None
    assert cache.get(second.repo_root, "bbb") is second


async def test_stale_repository_fails_closed() -> None:
    ri = FakeRI(state="stale", stale_paths=["auth/service.py"])
    with pytest.raises(SnapshotError, match="stale"):
        await build_snapshot(ri, cache=SnapshotCache())
    assert ri.call_count("get_architecture_summary") == 0


async def test_unindexed_repository_fails_closed() -> None:
    ri = FakeRI(state="unindexed", catalog_hash=None)  # type: ignore[arg-type]
    with pytest.raises(SnapshotError, match="unindexed"):
        await build_snapshot(ri, cache=SnapshotCache())
    assert ri.call_count("get_architecture_summary") == 0
