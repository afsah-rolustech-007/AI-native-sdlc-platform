"""ClaimSet → §B.2 RequirementsSpec. Pure, deterministic, no LLM, no RI.

`orchestration.state.RequirementsSpec` cannot be imported here: that module
loads LangGraph. This TypedDict is a structural copy of §B.2; tests lock the
field set against orchestration.state.
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from requirements_engine.claims import Claim, ClaimKind, ClaimSet, EpistemicStatus


class RequirementsSpec(TypedDict):
    functional: list[str]
    non_functional: dict[str, str]
    acceptance_criteria: list[str]
    open_ambiguities: list[str]
    assumptions: list[str]
    out_of_scope: list[str]
    version: int
    approved_at: datetime | None
    approved_by: str | None


def project_spec(claim_set: ClaimSet) -> RequirementsSpec:
    spec: RequirementsSpec = {
        "functional": [],
        "non_functional": {},
        "acceptance_criteria": [],
        "open_ambiguities": [],
        "assumptions": [],
        "out_of_scope": [],
        "version": 1,
        "approved_at": None,
        "approved_by": None,
    }
    for claim in claim_set.claims:
        _project_claim(claim, spec)
    if claim_set.extract_failed and not spec["open_ambiguities"]:
        spec["open_ambiguities"].append("extraction failed; request treated as unstructured")
    return spec


def _project_claim(claim: Claim, spec: RequirementsSpec) -> None:
    text = claim.text
    if claim.status == EpistemicStatus.CONTRADICTION:
        spec["open_ambiguities"].append(f"CONTRADICTION [{claim.id}]: {text}")
        return
    if claim.kind == ClaimKind.OUT_OF_SCOPE:
        spec["out_of_scope"].append(text)
        return
    if claim.status == EpistemicStatus.UNKNOWN:
        spec["open_ambiguities"].append(text)
        return
    if claim.status == EpistemicStatus.INFERENCE:
        spec["assumptions"].append(text)
        return
    if claim.status == EpistemicStatus.FACT and claim.provenance.source == "repository":
        spec["assumptions"].append(f"Repository fact: {text}")
        return
    if claim.kind == ClaimKind.NFR or (claim.kind == ClaimKind.CONSTRAINT and claim.nfr_type):
        key = claim.nfr_type or "unspecified"
        spec["non_functional"][key] = text
        return
    if claim.kind == ClaimKind.ACCEPTANCE:
        spec["acceptance_criteria"].append(text)
        return
    if claim.kind == ClaimKind.UNKNOWN and claim.status != EpistemicStatus.DECISION:
        spec["open_ambiguities"].append(text)
        return
    spec["functional"].append(text)
