"""ClaimSet and evidence types (Phase 04 §01).

Kind (what the claim is about) is independent of epistemic status (how we know it).
Repository PostgreSQL (FACT) + user "use MongoDB" (DECISION) is not a CONTRADICTION.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

RetrievedVia = Literal[
    "snapshot", "symbol", "lexical", "graph", "semantic", "manifest", "none"
]
ProvenanceSource = Literal["request", "engineer", "repository", "derived", "assumption"]


class ClaimKind(str, Enum):
    OBJECTIVE = "objective"
    FUNCTIONAL = "functional"
    CONSTRAINT = "constraint"
    NFR = "nfr"
    ACCEPTANCE = "acceptance"
    OUT_OF_SCOPE = "out_of_scope"
    REPO_DEPENDENT = "repo_dependent"
    UNKNOWN = "unknown"


class EpistemicStatus(str, Enum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    DECISION = "DECISION"
    UNKNOWN = "UNKNOWN"
    CONTRADICTION = "CONTRADICTION"


class Provenance(BaseModel):
    source: ProvenanceSource
    ref: str | None = None
    retrieved_via: RetrievedVia = "none"
    catalog_hash: str | None = None


class EvidenceRecord(BaseModel):
    """One retrieval result. This is evidence, not a classified claim.

    `unavailable=True` means the source could not be queried (for example Zoekt
    is missing). That is not the same as "zero hits".
    `accept_as` is a hint for later classification. Semantic hits are inference.
    """

    id: str
    signal: RetrievedVia
    query: str | None = None
    refs: list[str] = Field(default_factory=list)
    excerpt: str | None = None
    score: float | None = None
    catalog_hash: str | None = None
    cache_hit: bool = False
    latency_ms: float | None = None
    unavailable: bool = False
    unavailable_reason: str | None = None
    accept_as: Literal["fact", "inference"] | None = None
    ri_method: str | None = None
    result_count: int = 0


class Claim(BaseModel):
    id: str
    kind: ClaimKind
    text: str
    status: EpistemicStatus
    provenance: Provenance
    nfr_type: str | None = None
    # Optional hints for WorkflowContext. None = "this claim does not speak to the flag."
    touches_auth: bool | None = None
    touches_pii: bool | None = None
    touches_payments: bool | None = None
    has_database_changes: bool | None = None


class ClaimSet(BaseModel):
    claims: list[Claim] = Field(default_factory=list)
    raw_request: str = ""
    extract_failed: bool = False

    def by_status(self, status: EpistemicStatus) -> list[Claim]:
        return [claim for claim in self.claims if claim.status == status]


def is_fact_plus_decision(claim_set: ClaimSet) -> bool:
    """True when repo FACT and user DECISION coexist — not automatically a conflict."""
    statuses = {claim.status for claim in claim_set.claims}
    return EpistemicStatus.FACT in statuses and EpistemicStatus.DECISION in statuses


def has_contradiction(claim_set: ClaimSet) -> bool:
    return any(claim.status == EpistemicStatus.CONTRADICTION for claim in claim_set.claims)


def flag_contradiction(claim_set: ClaimSet, id_a: str, id_b: str) -> ClaimSet:
    """Mark two explicit decisions that cannot both hold. Does not invent new text."""
    ids = {id_a, id_b}
    updated: list[Claim] = []
    for claim in claim_set.claims:
        if claim.id in ids:
            if claim.status not in {EpistemicStatus.DECISION, EpistemicStatus.CONTRADICTION}:
                raise ValueError(
                    f"contradiction requires explicit decisions; {claim.id} is {claim.status}"
                )
            updated.append(claim.model_copy(update={"status": EpistemicStatus.CONTRADICTION}))
        else:
            updated.append(claim)
    found = {claim.id for claim in updated if claim.id in ids}
    if found != ids:
        raise KeyError(f"unknown claim ids for contradiction: {ids - found}")
    return claim_set.model_copy(update={"claims": updated})
