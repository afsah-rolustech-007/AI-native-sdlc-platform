"""Deterministic claim classification. No LLM. No RI.

User DECISION always wins over repository FACT. Semantic and graph hits are
INFERENCE only. FACT + DECISION is not a contradiction.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from requirements_engine.claims import (
    Claim,
    ClaimKind,
    ClaimSet,
    EpistemicStatus,
    EvidenceRecord,
    Provenance,
    flag_contradiction,
)
from requirements_engine.extractors import FACT_SIGNALS, WEAK_SIGNALS, usable_evidence
from requirements_engine.session import is_absence
from requirements_engine.snapshot import SessionRepoSnapshot

# Two explicit user/engineer DECISIONs that name opposite sides of a pair.
_EXCLUSIVE_PAIRS: tuple[tuple[frozenset[str], frozenset[str]], ...] = (
    (frozenset({"postgresql", "postgres"}), frozenset({"mongodb", "mongo"})),
    (frozenset({"mysql"}), frozenset({"postgresql", "postgres"})),
    (frozenset({"rest"}), frozenset({"graphql"})),
)
_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


class ClassifyNote(BaseModel):
    """Why one claim received its status. Kept for the audit trace."""

    claim_id: str
    status: EpistemicStatus
    reason: str


class ClassifyResult(BaseModel):
    claim_set: ClaimSet
    notes: list[ClassifyNote] = Field(default_factory=list)


def classify_claims(
    claim_set: ClaimSet,
    evidence: list[EvidenceRecord] | None = None,
    snapshot: SessionRepoSnapshot | None = None,
) -> ClassifyResult:
    """Reclassify claims from evidence. Never invents new requirement text."""
    records = list(evidence or [])
    notes: list[ClassifyNote] = []
    updated: list[Claim] = []
    for claim in claim_set.claims:
        classified, reason = _classify_one(claim, records, snapshot)
        notes.append(ClassifyNote(claim_id=classified.id, status=classified.status, reason=reason))
        updated.append(classified)
    result = claim_set.model_copy(update={"claims": updated})
    result, extra = _flag_exclusive_decisions(result)
    notes.extend(extra)
    return ClassifyResult(claim_set=result, notes=notes)


def _classify_one(
    claim: Claim,
    evidence: list[EvidenceRecord],
    snapshot: SessionRepoSnapshot | None,
) -> tuple[Claim, str]:
    if claim.status is EpistemicStatus.CONTRADICTION:
        return claim, "already marked CONTRADICTION"
    if _is_locked_decision(claim):
        return claim, "explicit user/engineer DECISION is never overwritten by repository evidence"

    quality, via, refs, catalog_hash = _best_support(claim, evidence, snapshot)
    if not _is_repository_claim(claim):
        # Request claims stay UNKNOWN/DECISION. JWT-in-repo is not "user wants JWT".
        return claim, "request claim is not upgraded from repository evidence"

    if quality == "fact":
        provenance = Provenance(
            source="repository",
            ref=refs[0] if refs else claim.provenance.ref,
            retrieved_via=via or claim.provenance.retrieved_via,
            catalog_hash=catalog_hash or claim.provenance.catalog_hash,
        )
        return (
            claim.model_copy(update={"status": EpistemicStatus.FACT, "provenance": provenance}),
            "deterministic repository evidence (snapshot/manifest/symbol/lexical)",
        )
    if quality == "inference":
        provenance = claim.provenance.model_copy(
            update={
                "retrieved_via": via or claim.provenance.retrieved_via,
                "catalog_hash": catalog_hash or claim.provenance.catalog_hash,
                "ref": refs[0] if refs else claim.provenance.ref,
            }
        )
        return (
            claim.model_copy(
                update={"status": EpistemicStatus.INFERENCE, "provenance": provenance}
            ),
            "semantic or weak graph evidence is INFERENCE, never FACT",
        )
    return claim, "no supporting evidence; UNKNOWN stays UNKNOWN"


def _is_locked_decision(claim: Claim) -> bool:
    return claim.status is EpistemicStatus.DECISION and claim.provenance.source in {
        "request",
        "engineer",
    }


def _is_repository_claim(claim: Claim) -> bool:
    return claim.kind is ClaimKind.REPO_DEPENDENT or claim.provenance.source == "repository"


def _best_support(
    claim: Claim,
    evidence: list[EvidenceRecord],
    snapshot: SessionRepoSnapshot | None,
) -> tuple[str | None, str | None, list[str], str | None]:
    """Return ('fact'|'inference'|None, retrieved_via, refs, catalog_hash)."""
    tokens = _tokens(claim.text)
    if snapshot is not None:
        snap_refs = _snapshot_support(snapshot, tokens)
        if snap_refs:
            return "fact", "snapshot", snap_refs, snapshot.catalog_hash
        manifest_refs = _manifest_support(snapshot, tokens)
        if manifest_refs:
            return "fact", "manifest", manifest_refs, snapshot.catalog_hash

    usable = usable_evidence(evidence)
    fact_hits = [
        item
        for item in usable
        if item.signal in FACT_SIGNALS
        and item.accept_as != "inference"
        and not is_absence(item)
        and item.refs
        and _overlap(tokens, item)
    ]
    if fact_hits:
        best = fact_hits[0]
        return "fact", best.signal, list(best.refs), best.catalog_hash

    weak_hits = [
        item
        for item in usable
        if (item.signal in WEAK_SIGNALS or item.accept_as == "inference")
        and item.refs
        and _overlap(tokens, item)
    ]
    if weak_hits:
        best = weak_hits[0]
        return "inference", best.signal, list(best.refs), best.catalog_hash
    return None, None, [], None


def _snapshot_support(snapshot: SessionRepoSnapshot, tokens: set[str]) -> list[str]:
    refs: list[str] = []
    for lang in snapshot.languages:
        if lang.lower() in tokens:
            refs.append(f"snapshot:languages:{lang}")
    for service in snapshot.services:
        if service.name.lower() in tokens:
            refs.append(f"service:{service.name}")
    for entity in snapshot.database_entities:
        if any(token in entity.lower() for token in tokens):
            refs.append(entity)
    return refs


def _manifest_support(snapshot: SessionRepoSnapshot, tokens: set[str]) -> list[str]:
    refs: list[str] = []
    for fact in snapshot.manifest_facts:
        for name in fact.names:
            lowered = name.lower()
            if any(token in lowered or lowered in token for token in tokens):
                refs.append(f"manifest:{fact.path}:{name}")
            if any(token.startswith("postgres") for token in tokens) and any(
                alias in lowered for alias in ("postgres", "psycopg", "asyncpg")
            ):
                refs.append(f"manifest:{fact.path}:{name}")
            if any(token.startswith("mongo") for token in tokens) and "mongo" in lowered:
                refs.append(f"manifest:{fact.path}:{name}")
    return list(dict.fromkeys(refs))


def _overlap(tokens: set[str], item: EvidenceRecord) -> bool:
    haystack = " ".join([item.query or "", item.excerpt or "", *item.refs]).lower()
    if not tokens:
        return bool(item.refs)
    return any(token in haystack for token in tokens)


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in _TOKEN.finditer(text) if len(match.group(0)) >= 3}


def _flag_exclusive_decisions(claim_set: ClaimSet) -> tuple[ClaimSet, list[ClassifyNote]]:
    """Only two explicit DECISIONs can contradict. Repo FACT vs user DECISION cannot."""
    decisions = [
        claim
        for claim in claim_set.claims
        if claim.status is EpistemicStatus.DECISION
        and claim.provenance.source in {"request", "engineer"}
    ]
    notes: list[ClassifyNote] = []
    flagged: set[str] = set()
    result = claim_set
    for left, right in _EXCLUSIVE_PAIRS:
        a = next((c for c in decisions if _has_any(c, left) and c.id not in flagged), None)
        b = next((c for c in decisions if _has_any(c, right) and c.id not in flagged), None)
        if a is None or b is None or a.id == b.id:
            continue
        result = flag_contradiction(result, a.id, b.id)
        flagged.update({a.id, b.id})
        reason = f"explicit DECISIONs {a.id} and {b.id} cannot both hold"
        notes.append(
            ClassifyNote(claim_id=a.id, status=EpistemicStatus.CONTRADICTION, reason=reason)
        )
        notes.append(
            ClassifyNote(claim_id=b.id, status=EpistemicStatus.CONTRADICTION, reason=reason)
        )
    return result, notes


def _has_any(claim: Claim, needles: frozenset[str]) -> bool:
    tokens = _tokens(claim.text)
    return any(
        needle in tokens or any(token.startswith(needle) for token in tokens) for needle in needles
    )
