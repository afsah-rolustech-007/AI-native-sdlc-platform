"""Phase 03 RI signal adapters. Never pass refresh=True. Never fuse signals."""

from __future__ import annotations

import time
from typing import Any

from common.telemetry import TelemetrySink
from repo_intel.exceptions import (
    EmbeddingIndexError,
    EmbeddingsNotIndexedError,
    GraphNotBuiltError,
    RepoIntelError,
    StaleIndexError,
    SymbolNotFoundError,
    ZoektNotIndexedError,
    ZoektSearchError,
    ZoektUnavailableError,
)
from requirements_engine.claims import ClaimSet, EvidenceRecord
from requirements_engine.plans import PlanMethod
from requirements_engine.ri_client import RepoIntelClient
from requirements_engine.session import (
    CacheBox,
    RetrievalSession,
    make_record,
    trace_method,
    unavailable_record,
)
from requirements_engine.snapshot import SessionRepoSnapshot, snapshot_paths_for_query

SEMANTIC_TOP_K = 3
LEXICAL_TOP_K = 10
_LEXICAL_DOWN = (ZoektUnavailableError, ZoektNotIndexedError, ZoektSearchError)
_SEMANTIC_DOWN = (EmbeddingsNotIndexedError, EmbeddingIndexError)
_GRAPH_DOWN = (GraphNotBuiltError,)


async def run_symbol(
    method: PlanMethod,
    query: str,
    accept: str,
    snapshot: SessionRepoSnapshot,
    ri: RepoIntelClient,
    session: RetrievalSession,
    claims: ClaimSet | None,
    sink: TelemetrySink,
) -> list[EvidenceRecord]:
    symbol_id = _resolve_symbol_id(method, claims)
    if symbol_id:
        return await _symbol_by_id(method, query, accept, snapshot, ri, session, sink, symbol_id)
    if method.file_path:
        return await _file_structure(method, query, accept, snapshot, ri, session, sink)
    trace_method(session, method, query=query, error="missing_symbol_id")
    return []


async def run_lexical(
    method: PlanMethod,
    query: str,
    accept: str,
    snapshot: SessionRepoSnapshot,
    ri: RepoIntelClient,
    session: RetrievalSession,
    sink: TelemetrySink,
) -> list[EvidenceRecord]:
    top_k = method.top_k or LEXICAL_TOP_K
    key = cache_key("lexical", query, extra=str(top_k), catalog_hash=snapshot.catalog_hash)
    hits, err, cache_hit, latency = await call_ri(
        session, key, sink, "search_codebase", lambda: ri.search_codebase(query, top_k)
    )
    if isinstance(err, StaleIndexError):
        raise err
    if err is not None:
        if isinstance(err, _LEXICAL_DOWN):
            session.zoekt = "unavailable"
        record = unavailable_record(
            session, method, query, accept, err, "search_codebase", cache_hit
        )
        trace_method(
            session,
            method,
            query=query,
            ri_method="search_codebase",
            cache_hit=cache_hit,
            unavailable=True,
            error=type(err).__name__,
        )
        return [record]
    session.zoekt = "available"
    rows = list(hits or [])
    records = [
        make_record(
            session,
            method,
            query,
            accept,
            refs=[_hit_ref(item)],
            excerpt=getattr(item, "snippet", None),
            score=getattr(item, "score", None),
            ri_method="search_codebase",
            cache_hit=cache_hit,
            latency_ms=latency,
            result_count=1,
        )
        for item in rows
    ]
    if not records:
        records = [
            make_record(
                session,
                method,
                query,
                accept,
                ri_method="search_codebase",
                cache_hit=cache_hit,
                latency_ms=latency,
                result_count=0,
            )
        ]
    trace_method(
        session,
        method,
        query=query,
        ri_method="search_codebase",
        cache_hit=cache_hit,
        result_count=len(rows),
    )
    return records


async def run_semantic(
    method: PlanMethod,
    query: str,
    snapshot: SessionRepoSnapshot,
    ri: RepoIntelClient,
    session: RetrievalSession,
    sink: TelemetrySink,
) -> list[EvidenceRecord]:
    # Semantic relatedness is never FACT, even if the plan's accept_as is fact.
    accept = "inference"
    top_k = method.top_k or SEMANTIC_TOP_K
    paths = snapshot_paths_for_query(snapshot, query) if method.paths_from_snapshot else None
    key = cache_key(
        "semantic",
        query,
        paths=tuple(paths or ()),
        extra=f"{top_k}:{method.min_score}",
        catalog_hash=snapshot.catalog_hash,
    )

    async def _call() -> Any:
        return await ri.search_concepts(
            query, top_k, kinds=None, paths=paths, min_score=method.min_score
        )

    hits, err, cache_hit, latency = await call_ri(session, key, sink, "search_concepts", _call)
    if isinstance(err, StaleIndexError):
        raise err
    if err is not None:
        if isinstance(err, _SEMANTIC_DOWN):
            session.embeddings = "unavailable"
        record = unavailable_record(
            session, method, query, accept, err, "search_concepts", cache_hit
        )
        trace_method(
            session,
            method,
            query=query,
            ri_method="search_concepts",
            cache_hit=cache_hit,
            unavailable=True,
            error=type(err).__name__,
        )
        return [record]
    session.embeddings = "available"
    rows = list(hits or [])
    records = [
        make_record(
            session,
            method,
            query,
            accept,
            refs=[str(getattr(item, "symbol_id", None) or getattr(item, "file_path", "") or "")],
            excerpt=getattr(item, "chunk_text", None),
            score=getattr(item, "score", None),
            ri_method="search_concepts",
            cache_hit=cache_hit,
            latency_ms=latency,
            result_count=1,
        )
        for item in rows
    ]
    if not records:
        records = [
            make_record(
                session,
                method,
                query,
                accept,
                ri_method="search_concepts",
                cache_hit=cache_hit,
                latency_ms=latency,
                result_count=0,
            )
        ]
    trace_method(
        session,
        method,
        query=query,
        ri_method="search_concepts",
        cache_hit=cache_hit,
        result_count=len(rows),
    )
    return records


async def run_graph(
    method: PlanMethod,
    query: str,
    accept: str,
    snapshot: SessionRepoSnapshot,
    ri: RepoIntelClient,
    session: RetrievalSession,
    claims: ClaimSet | None,
    sink: TelemetrySink,
) -> list[EvidenceRecord]:
    op = method.graph_op or "impact"
    symbol_id = _resolve_symbol_id(method, claims)
    file_path = method.file_path
    depth = method.depth if method.depth is not None else 1
    ri_method, factory, target = _graph_call(ri, op, symbol_id, file_path, depth, query)
    if factory is None:
        trace_method(session, method, query=query, error="missing_graph_target")
        return []
    key = cache_key("graph", target, extra=f"{op}:{depth}", catalog_hash=snapshot.catalog_hash)
    hits, err, cache_hit, latency = await call_ri(session, key, sink, ri_method, factory)
    if isinstance(err, StaleIndexError):
        raise err
    if err is not None:
        if isinstance(err, _GRAPH_DOWN):
            session.graph = "unavailable"
        record = unavailable_record(session, method, query, accept, err, ri_method, cache_hit)
        trace_method(
            session,
            method,
            query=target,
            ri_method=ri_method,
            cache_hit=cache_hit,
            unavailable=True,
            error=type(err).__name__,
        )
        return [record]
    refs = _graph_refs(hits)
    record = make_record(
        session,
        method,
        query,
        accept,
        refs=refs,
        ri_method=ri_method,
        cache_hit=cache_hit,
        latency_ms=latency,
        result_count=len(refs),
    )
    trace_method(
        session,
        method,
        query=target,
        ri_method=ri_method,
        cache_hit=cache_hit,
        result_count=len(refs),
    )
    return [record]


async def call_ri(
    session: RetrievalSession,
    key: tuple[Any, ...],
    sink: TelemetrySink,
    name: str,
    factory: Any,
) -> tuple[Any, BaseException | None, bool, float | None]:
    """Call RI once. Cache hits do not count against the session budget."""
    cached = session.cache.get(key)
    if cached is not None:
        return cached.value, cached.error, True, 0.0
    if session.remaining_budget <= 0:
        return None, RuntimeError("budget"), False, None
    session.ri_calls += 1
    started = time.perf_counter()
    with sink.span(
        kind="tool_call",
        name=name,
        task_id=session.task_id,
        phase="requirements",
        attributes={"ri_method": name, "catalog_hash": session.snapshot.catalog_hash},
    ):
        try:
            result = await factory()
        except StaleIndexError:
            raise
        except RepoIntelError as exc:
            latency = (time.perf_counter() - started) * 1000
            session.cache[key] = CacheBox(error=exc)
            return None, exc, False, latency
    latency = (time.perf_counter() - started) * 1000
    session.cache[key] = CacheBox(value=result)
    return result, None, False, latency


def cache_key(
    signal: str,
    query: str,
    *,
    paths: tuple[str, ...] = (),
    kinds: tuple[str, ...] = (),
    extra: str = "",
    catalog_hash: str,
) -> tuple[Any, ...]:
    normalized = " ".join(query.lower().split())
    return (signal, normalized, paths, kinds, extra, catalog_hash)


async def _symbol_by_id(
    method: PlanMethod,
    query: str,
    accept: str,
    snapshot: SessionRepoSnapshot,
    ri: RepoIntelClient,
    session: RetrievalSession,
    sink: TelemetrySink,
    symbol_id: str,
) -> list[EvidenceRecord]:
    key = cache_key("symbol", symbol_id, catalog_hash=snapshot.catalog_hash)
    hits, err, cache_hit, latency = await call_ri(
        session,
        key,
        sink,
        "get_symbol_signature",
        lambda: ri.get_symbol_signature(symbol_id),
    )
    if isinstance(err, StaleIndexError):
        raise err
    if isinstance(err, SymbolNotFoundError):
        # Absence of this id is evidence. It is not evidence the concept is missing.
        record = make_record(
            session,
            method,
            query,
            accept,
            refs=[f"absent:{symbol_id}"],
            excerpt=str(err),
            ri_method="get_symbol_signature",
            cache_hit=cache_hit,
            latency_ms=latency,
            result_count=0,
        )
        trace_method(
            session,
            method,
            query=symbol_id,
            ri_method="get_symbol_signature",
            cache_hit=cache_hit,
            result_count=0,
        )
        return [record]
    if err is not None:
        return [
            unavailable_record(
                session, method, query, accept, err, "get_symbol_signature", cache_hit
            )
        ]
    record = make_record(
        session,
        method,
        query,
        accept,
        refs=[symbol_id],
        excerpt=str(hits),
        ri_method="get_symbol_signature",
        cache_hit=cache_hit,
        latency_ms=latency,
        result_count=1,
    )
    trace_method(
        session,
        method,
        query=symbol_id,
        ri_method="get_symbol_signature",
        cache_hit=cache_hit,
        result_count=1,
    )
    return [record]


async def _file_structure(
    method: PlanMethod,
    query: str,
    accept: str,
    snapshot: SessionRepoSnapshot,
    ri: RepoIntelClient,
    session: RetrievalSession,
    sink: TelemetrySink,
) -> list[EvidenceRecord]:
    file_path = method.file_path or ""
    key = cache_key("file_structure", file_path, catalog_hash=snapshot.catalog_hash)
    hits, err, cache_hit, latency = await call_ri(
        session, key, sink, "get_file_structure", lambda: ri.get_file_structure(file_path)
    )
    if isinstance(err, StaleIndexError):
        raise err
    if err is not None:
        return [
            unavailable_record(session, method, query, accept, err, "get_file_structure", cache_hit)
        ]
    symbols = list(hits or [])
    refs = [getattr(item, "id", str(item)) for item in symbols]
    record = make_record(
        session,
        method,
        query,
        accept,
        refs=refs,
        ri_method="get_file_structure",
        cache_hit=cache_hit,
        latency_ms=latency,
        result_count=len(refs),
    )
    trace_method(
        session,
        method,
        query=file_path,
        ri_method="get_file_structure",
        cache_hit=cache_hit,
        result_count=len(refs),
    )
    return [record]


def _graph_call(
    ri: RepoIntelClient,
    op: str,
    symbol_id: str | None,
    file_path: str | None,
    depth: int,
    query: str,
) -> tuple[str, Any, str]:
    if op == "callers" and symbol_id:
        return "get_callers", lambda: ri.get_callers(symbol_id, depth=depth), symbol_id
    if op == "callees" and symbol_id:
        return "get_callees", lambda: ri.get_callees(symbol_id, depth=depth), symbol_id
    if op == "dependencies" and file_path:
        return "get_dependencies", lambda: ri.get_dependencies(file_path), file_path
    if op == "dependents" and file_path:
        return "get_dependents", lambda: ri.get_dependents(file_path), file_path
    if op == "impact":
        files = [file_path] if file_path else [query]
        return "get_impact_set", lambda: ri.get_impact_set(files, depth=depth), ",".join(files)
    return op, None, query


def _resolve_symbol_id(method: PlanMethod, claims: ClaimSet | None) -> str | None:
    if method.symbol_id:
        return method.symbol_id
    if method.symbol_id_from and claims:
        for claim in claims.claims:
            if claim.id == method.symbol_id_from:
                return claim.provenance.ref or claim.text
    return None


def _hit_ref(item: object) -> str:
    path = getattr(item, "file_path", None) or ""
    line = getattr(item, "line", None)
    if path and line is not None:
        return f"{path}:{line}"
    return str(path or item)


def _graph_refs(hits: object) -> list[str]:
    if hits is None:
        return []
    affected = getattr(hits, "affected_files", None)
    if affected is not None:
        symbols = getattr(hits, "affected_symbols", None) or []
        return [str(item) for item in list(affected) + list(symbols)]
    if isinstance(hits, list):
        refs: list[str] = []
        for item in hits:
            if isinstance(item, str):
                refs.append(item)
            else:
                refs.append(
                    str(getattr(item, "id", None) or getattr(item, "file_path", None) or item)
                )
        return refs
    return [str(hits)]
