"""Typed extractors: deterministic facts vs weak graph inference."""

from __future__ import annotations

from requirements_engine.claims import EvidenceRecord
from requirements_engine.extractors import run_extractor
from requirements_engine.manifests import ManifestFact
from requirements_engine.snapshot import ServiceSlice, SessionRepoSnapshot


def _snapshot(**kwargs: object) -> SessionRepoSnapshot:
    return SessionRepoSnapshot(
        repo_root="/tmp/repo",
        catalog_hash="hash1",
        file_count=4,
        index_state="fresh",
        **kwargs,  # type: ignore[arg-type]
    )


def test_graph_neighborhood_is_inference_not_fact() -> None:
    evidence = [
        EvidenceRecord(
            id="e1",
            signal="graph",
            query="auth",
            refs=["web/main.py"],
            ri_method="get_dependents",
            accept_as="fact",
            result_count=1,
        )
    ]
    hit = run_extractor("neighborhood_nonempty", snapshot=None, evidence=evidence)
    assert hit is not None
    assert hit.status == "inference"
    assert hit.confidence == "low"


def test_semantic_records_are_ignored_by_fact_extractors() -> None:
    snapshot = _snapshot(services=[ServiceSlice(name="billing", files=1)])
    evidence = [
        EvidenceRecord(
            id="e1",
            signal="semantic",
            query="auth",
            refs=["auth/service.py::AuthService"],
            accept_as="inference",
            result_count=1,
        )
    ]
    hit = run_extractor("service_exists", snapshot=snapshot, evidence=evidence, query="auth")
    assert hit is None


def test_declared_database_maps_psycopg_to_postgresql() -> None:
    snapshot = _snapshot(
        manifest_facts=[ManifestFact(path="pyproject.toml", names=["psycopg", "fastapi"])]
    )
    hit = run_extractor("declared_database", snapshot=snapshot, evidence=[])
    assert hit is not None
    assert hit.status == "fact"
    assert "postgresql" in hit.answer.lower()
    assert hit.refs
    assert all("fastapi" not in ref.lower() for ref in hit.refs)
