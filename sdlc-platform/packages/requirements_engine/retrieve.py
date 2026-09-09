"""Targeted RI retrieval for an EvidencePlan.

Need-driven: run the plan's methods in order, stop when an extractor accepts.
In-session cache avoids repeating the same RI query. Budgets cap RI calls.
Zoekt/embeddings errors are recorded as unavailable — never as zero hits.
Semantic hits are always `accept_as=inference`. We never call
find_relevant_context and we never pass refresh=True.
"""

from __future__ import annotations

from typing import Any

from common.telemetry import NoOpTelemetrySink, TelemetrySink
from repo_intel.exceptions import StaleIndexError
from requirements_engine.claims import ClaimSet, EvidenceRecord
from requirements_engine.plans import RI_SIGNALS, EvidencePlan, PlanMethod, parse_evidence_plan
from requirements_engine.ri_client import RepoIntelClient
from requirements_engine.ri_signals import run_graph, run_lexical, run_semantic, run_symbol
from requirements_engine.session import (
    SESSION_RI_BUDGET,
    RetrievalSession,
    RetrievalTrace,
    is_absence,
    make_record,
    trace_method,
)
from requirements_engine.snapshot import (
    SessionRepoSnapshot,
    refs_from_manifests,
    refs_from_snapshot,
)

__all__ = [
    "SESSION_RI_BUDGET",
    "RetrievalSession",
    "RetrievalTrace",
    "execute_plan",
    "extractor_accepts",
]


async def execute_plan(
    plan: EvidencePlan | dict[str, Any],
    snapshot: SessionRepoSnapshot,
    ri: RepoIntelClient,
    session: RetrievalSession,
    claims: ClaimSet | None = None,
    *,
    sink: TelemetrySink | None = None,
) -> list[EvidenceRecord]:
    """Run methods in order. Stop when the named extractor accepts the hits."""
    parsed = plan if isinstance(plan, EvidencePlan) else parse_evidence_plan(plan)
    if snapshot.catalog_hash != session.snapshot.catalog_hash:
        raise StaleIndexError(
            [],
            "snapshot catalog_hash no longer matches the retrieval session",
        )
    telemetry = sink or NoOpTelemetrySink()
    collected: list[EvidenceRecord] = []
    plan_ri_before = session.ri_calls
    for method in parsed.methods:
        if session.ri_calls - plan_ri_before >= parsed.max_ri_calls:
            break
        if method.signal in RI_SIGNALS and session.remaining_budget <= 0:
            trace_method(
                session, method, query=_resolve_query(method, parsed, claims), error="budget"
            )
            break
        records = await _run_method(method, parsed, snapshot, ri, session, claims, telemetry)
        collected.extend(records)
        if extractor_accepts(method, records, snapshot):
            break
    return collected


def extractor_accepts(
    method: PlanMethod,
    records: list[EvidenceRecord],
    snapshot: SessionRepoSnapshot,
) -> bool:
    """Presence check only. Does not write FACT/DECISION (that is Group C)."""
    usable = [item for item in records if not item.unavailable]
    name = method.extractor
    if name is None:
        return any(item.refs and not is_absence(item) for item in usable)
    if name == "service_exists":
        return any(ref.startswith("service:") for item in usable for ref in item.refs)
    if name == "database_entities_present":
        return bool(snapshot.database_entities)
    if name == "symbol_exists":
        found = any(item.ri_method == "get_symbol_signature" and item.refs for item in usable)
        return found and not any(is_absence(item) for item in usable)
    if name == "identifier_in_snippet":
        needle = (method.query or "").lower()
        return any(
            (needle and needle in (item.excerpt or "").lower()) or bool(item.refs)
            for item in usable
        )
    if name == "neighborhood_nonempty":
        return any(item.result_count > 0 and item.refs for item in usable)
    if name == "dependency_declared":
        return any(ref.startswith("manifest:") for item in usable for ref in item.refs)
    if name == "languages_from_snapshot":
        return bool(snapshot.languages)
    if name == "declared_database":
        blob = " ".join(name for fact in snapshot.manifest_facts for name in fact.names).lower()
        tokens = ("postgres", "psycopg", "asyncpg", "mysql", "mongo", "sqlite")
        return any(token in blob for token in tokens)
    return any(item.refs for item in usable)


async def _run_method(
    method: PlanMethod,
    plan: EvidencePlan,
    snapshot: SessionRepoSnapshot,
    ri: RepoIntelClient,
    session: RetrievalSession,
    claims: ClaimSet | None,
    sink: TelemetrySink,
) -> list[EvidenceRecord]:
    query = _resolve_query(method, plan, claims)
    accept = "inference" if method.signal == "semantic" else plan.accept_as
    if method.signal == "snapshot":
        refs = refs_from_snapshot(snapshot, query)
        records = [make_record(session, method, query, accept, refs=refs)]
        trace_method(session, method, query=query, result_count=len(refs))
        return records
    if method.signal == "manifest":
        refs = refs_from_manifests(snapshot, query)
        records = [make_record(session, method, query, accept, refs=refs)]
        trace_method(session, method, query=query, result_count=len(refs))
        return records
    if method.budget <= 0:
        trace_method(session, method, query=query, error="method_budget")
        return []
    if method.signal == "symbol":
        return await run_symbol(method, query, accept, snapshot, ri, session, claims, sink)
    if method.signal == "lexical":
        return await run_lexical(method, query, accept, snapshot, ri, session, sink)
    if method.signal == "semantic":
        return await run_semantic(method, query, snapshot, ri, session, sink)
    if method.signal == "graph":
        return await run_graph(method, query, accept, snapshot, ri, session, claims, sink)
    return []


def _resolve_query(method: PlanMethod, plan: EvidencePlan, claims: ClaimSet | None) -> str:
    if method.query:
        return method.query
    if method.query_from_claims and claims:
        for claim in claims.claims:
            if claim.id == method.query_from_claims:
                return claim.text
    return plan.need.replace("_", " ")
