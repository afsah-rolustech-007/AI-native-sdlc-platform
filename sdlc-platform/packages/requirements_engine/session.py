"""Per-session retrieval budget, query cache, and evidence-record helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from requirements_engine.claims import EvidenceRecord
from requirements_engine.plans import PlanMethod
from requirements_engine.snapshot import SessionRepoSnapshot

SESSION_RI_BUDGET = 16
MAX_EXCERPT = 240


@dataclass
class CacheBox:
    """Raw RI result or error. A cache hit must not count as a new RI call."""

    value: Any = None
    error: BaseException | None = None


@dataclass
class RetrievalTrace:
    """One method attempt. Later used for evaluation / Phase 15 labels."""

    signal: str
    ri_method: str | None
    query: str
    cache_hit: bool
    result_count: int
    budget_used: int
    error: str | None = None
    unavailable: bool = False


@dataclass
class RetrievalSession:
    """Per-session RI budget, query cache, and traces."""

    snapshot: SessionRepoSnapshot
    session_budget: int = SESSION_RI_BUDGET
    task_id: str = "requirements-session"
    cache: dict[tuple[Any, ...], CacheBox] = field(default_factory=dict)
    traces: list[RetrievalTrace] = field(default_factory=list)
    ri_calls: int = 0
    evidence_seq: int = 0
    zoekt: str = "unknown"
    embeddings: str = "unknown"
    graph: str = "available"

    @property
    def remaining_budget(self) -> int:
        return max(0, self.session_budget - self.ri_calls)

    def next_id(self) -> str:
        self.evidence_seq += 1
        return f"ev-{self.evidence_seq:04d}"


def make_record(
    session: RetrievalSession,
    method: PlanMethod,
    query: str,
    accept: str,
    *,
    refs: list[str] | None = None,
    excerpt: str | None = None,
    score: float | None = None,
    ri_method: str | None = None,
    cache_hit: bool = False,
    latency_ms: float | None = None,
    result_count: int | None = None,
    unavailable: bool = False,
    unavailable_reason: str | None = None,
) -> EvidenceRecord:
    refs = [item for item in (refs or []) if item]
    return EvidenceRecord(
        id=session.next_id(),
        signal=method.signal,  # type: ignore[arg-type]
        query=query,
        refs=refs,
        excerpt=_excerpt(excerpt),
        score=score,
        catalog_hash=session.snapshot.catalog_hash,
        cache_hit=cache_hit,
        latency_ms=latency_ms,
        unavailable=unavailable,
        unavailable_reason=unavailable_reason,
        accept_as=accept,  # type: ignore[arg-type]
        ri_method=ri_method,
        result_count=len(refs) if result_count is None else result_count,
    )


def unavailable_record(
    session: RetrievalSession,
    method: PlanMethod,
    query: str,
    accept: str,
    err: BaseException,
    ri_method: str,
    cache_hit: bool = False,
) -> EvidenceRecord:
    return make_record(
        session,
        method,
        query,
        accept,
        ri_method=ri_method,
        cache_hit=cache_hit,
        unavailable=True,
        unavailable_reason=f"{type(err).__name__}: {err}",
        result_count=0,
    )


def trace_method(
    session: RetrievalSession,
    method: PlanMethod,
    *,
    query: str,
    ri_method: str | None = None,
    cache_hit: bool = False,
    result_count: int = 0,
    error: str | None = None,
    unavailable: bool = False,
) -> None:
    session.traces.append(
        RetrievalTrace(
            signal=method.signal,
            ri_method=ri_method,
            query=query,
            cache_hit=cache_hit,
            result_count=result_count,
            budget_used=session.ri_calls,
            error=error,
            unavailable=unavailable,
        )
    )


def is_absence(record: EvidenceRecord) -> bool:
    return any(ref.startswith("absent:") for ref in record.refs)


def _excerpt(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= MAX_EXCERPT:
        return cleaned
    return cleaned[: MAX_EXCERPT - 1] + "…"
