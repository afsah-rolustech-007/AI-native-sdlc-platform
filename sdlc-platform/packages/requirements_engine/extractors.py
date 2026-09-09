"""Typed extractors over snapshot + evidence. No RI calls. No LLM.

Each extractor answers a *repository situation* need (languages, declared
dependency, symbol id). They do not decide what the engineer wants.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from requirements_engine.claims import EvidenceRecord
from requirements_engine.session import is_absence
from requirements_engine.snapshot import SessionRepoSnapshot

# Deterministic name → database. Manifest tokens only, never guessed from prose.
_DATABASE_ALIASES: dict[str, tuple[str, ...]] = {
    "postgresql": ("postgresql", "postgres", "psycopg", "psycopg2", "asyncpg"),
    "mongodb": ("mongodb", "pymongo"),
    "mysql": ("mysql", "pymysql", "mysqlclient"),
    "sqlite": ("sqlite", "sqlite3", "aiosqlite"),
}

FACT_SIGNALS = frozenset({"snapshot", "manifest", "symbol", "lexical"})
WEAK_SIGNALS = frozenset({"semantic", "graph"})


class ExtractorHit(BaseModel):
    """One extractor result. `status=inference` must not close a human slot."""

    extractor: str
    answer: str
    refs: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]
    status: Literal["fact", "inference"]
    reason: str


def usable_evidence(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """Skip unavailable sources. Unavailable is not zero hits."""
    return [item for item in records if not item.unavailable]


def fact_evidence(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """Signals that may support FACT. Semantic and graph are excluded."""
    return [
        item
        for item in usable_evidence(records)
        if item.signal in FACT_SIGNALS and item.accept_as != "inference"
    ]


def run_extractor(
    name: str,
    *,
    snapshot: SessionRepoSnapshot | None,
    evidence: list[EvidenceRecord],
    query: str | None = None,
) -> ExtractorHit | None:
    """Dispatch a named extractor. Unknown names return None (fail closed)."""
    runners = {
        "languages_from_snapshot": _languages,
        "service_exists": _service_exists,
        "database_entities_present": _database_entities,
        "declared_database": _declared_database,
        "dependency_declared": _dependency_declared,
        "symbol_exists": _symbol_exists,
        "identifier_in_snippet": _identifier_in_snippet,
        "neighborhood_nonempty": _neighborhood,
    }
    runner = runners.get(name)
    if runner is None:
        return None
    return runner(snapshot=snapshot, evidence=evidence, query=query)


def _languages(
    *,
    snapshot: SessionRepoSnapshot | None,
    evidence: list[EvidenceRecord],
    query: str | None,
) -> ExtractorHit | None:
    del evidence, query
    if snapshot is None or not snapshot.languages:
        return None
    langs = ", ".join(snapshot.languages)
    return ExtractorHit(
        extractor="languages_from_snapshot",
        answer=f"Repository languages: {langs}",
        refs=[f"snapshot:languages:{item}" for item in snapshot.languages],
        confidence="high",
        status="fact",
        reason="snapshot tech_stack is file-suffix languages, not frameworks",
    )


def _service_exists(
    *,
    snapshot: SessionRepoSnapshot | None,
    evidence: list[EvidenceRecord],
    query: str | None,
) -> ExtractorHit | None:
    if snapshot is None:
        return None
    needle = (query or "").strip().lower()
    matches = [
        service
        for service in snapshot.services
        if not needle or needle in service.name.lower()
    ]
    refs = [f"service:{service.name}" for service in matches]
    for item in fact_evidence(evidence):
        refs.extend(ref for ref in item.refs if ref.startswith("service:"))
    refs = _dedupe(refs)
    if not refs:
        return None
    names = [ref.split(":", 1)[-1] for ref in refs]
    return ExtractorHit(
        extractor="service_exists",
        answer=f"Repository has service(s): {', '.join(names)}",
        refs=refs,
        confidence="high",
        status="fact",
        reason="service name is present on the session snapshot",
    )


def _database_entities(
    *,
    snapshot: SessionRepoSnapshot | None,
    evidence: list[EvidenceRecord],
    query: str | None,
) -> ExtractorHit | None:
    del query
    entities = list(snapshot.database_entities) if snapshot is not None else []
    for item in fact_evidence(evidence):
        entities.extend(item.refs)
    entities = _dedupe(entities)
    if not entities:
        return None
    return ExtractorHit(
        extractor="database_entities_present",
        answer=f"Repository database entities: {', '.join(entities)}",
        refs=entities,
        confidence="high",
        status="fact",
        reason="snapshot database_entities list is non-empty",
    )


def _declared_database(
    *,
    snapshot: SessionRepoSnapshot | None,
    evidence: list[EvidenceRecord],
    query: str | None,
) -> ExtractorHit | None:
    del query
    blob_parts: list[str] = []
    refs: list[str] = []
    if snapshot is not None:
        for fact in snapshot.manifest_facts:
            for name in fact.names:
                blob_parts.append(name.lower())
                refs.append(f"manifest:{fact.path}:{name}")
    for item in fact_evidence(evidence):
        blob_parts.extend(ref.lower() for ref in item.refs)
        blob_parts.append((item.excerpt or "").lower())
        refs.extend(item.refs)
    blob = " ".join(blob_parts)
    found: list[str] = []
    for canonical, aliases in _DATABASE_ALIASES.items():
        if any(alias in blob for alias in aliases):
            found.append(canonical)
    found = _dedupe(found)
    if not found:
        return None
    alias_needles = [alias for name in found for alias in _DATABASE_ALIASES[name]]
    matched_refs = [
        ref for ref in refs if any(alias in ref.lower() for alias in alias_needles)
    ]
    return ExtractorHit(
        extractor="declared_database",
        answer=f"Repository declares database technology: {', '.join(found)}",
        refs=matched_refs or _dedupe(refs)[:8],
        confidence="high",
        status="fact",
        reason="dependency name in an allowlisted manifest",
    )


def _dependency_declared(
    *,
    snapshot: SessionRepoSnapshot | None,
    evidence: list[EvidenceRecord],
    query: str | None,
) -> ExtractorHit | None:
    needle = (query or "").strip().lower()
    refs: list[str] = []
    names: list[str] = []
    if snapshot is not None:
        for fact in snapshot.manifest_facts:
            for name in fact.names:
                if not needle or needle in name.lower():
                    names.append(name)
                    refs.append(f"manifest:{fact.path}:{name}")
    for item in fact_evidence(evidence):
        for ref in item.refs:
            if ref.startswith("manifest:") and (not needle or needle in ref.lower()):
                refs.append(ref)
                names.append(ref.rsplit(":", 1)[-1])
    refs, names = _dedupe(refs), _dedupe(names)
    if not names:
        return None
    return ExtractorHit(
        extractor="dependency_declared",
        answer=f"Repository declares dependency: {', '.join(names)}",
        refs=refs,
        confidence="high",
        status="fact",
        reason="allowlisted manifest lists this package name",
    )


def _symbol_exists(
    *,
    snapshot: SessionRepoSnapshot | None,
    evidence: list[EvidenceRecord],
    query: str | None,
) -> ExtractorHit | None:
    del snapshot, query
    hits = [
        item
        for item in fact_evidence(evidence)
        if item.ri_method == "get_symbol_signature" and item.refs and not is_absence(item)
    ]
    if not hits:
        return None
    refs = _dedupe([ref for item in hits for ref in item.refs])
    return ExtractorHit(
        extractor="symbol_exists",
        answer=f"Symbol exists: {', '.join(refs)}",
        refs=refs,
        confidence="high",
        status="fact",
        reason="get_symbol_signature returned a signature",
    )


def _identifier_in_snippet(
    *,
    snapshot: SessionRepoSnapshot | None,
    evidence: list[EvidenceRecord],
    query: str | None,
) -> ExtractorHit | None:
    del snapshot
    needle = (query or "").strip().lower()
    hits = [item for item in fact_evidence(evidence) if item.signal == "lexical"]
    if needle:
        hits = [
            item
            for item in hits
            if needle in (item.excerpt or "").lower() or any(needle in ref.lower() for ref in item.refs)
        ]
    if not hits:
        return None
    refs = _dedupe([ref for item in hits for ref in item.refs])
    label = needle or "identifier"
    return ExtractorHit(
        extractor="identifier_in_snippet",
        answer=f"Identifier {label!r} appears in the repository",
        refs=refs,
        confidence="medium",
        status="fact",
        reason="lexical hit for an exact identifier — not a user decision",
    )


def _neighborhood(
    *,
    snapshot: SessionRepoSnapshot | None,
    evidence: list[EvidenceRecord],
    query: str | None,
) -> ExtractorHit | None:
    del snapshot, query
    hits = [item for item in usable_evidence(evidence) if item.signal == "graph" and item.refs]
    if not hits:
        return None
    refs = _dedupe([ref for item in hits for ref in item.refs])
    return ExtractorHit(
        extractor="neighborhood_nonempty",
        answer=f"Graph neighborhood is non-empty: {', '.join(refs[:8])}",
        refs=refs,
        confidence="low",
        status="inference",
        reason="graph relatedness is weak evidence and cannot become FACT",
    )


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
