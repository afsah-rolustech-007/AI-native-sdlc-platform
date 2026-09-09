"""Minimal, pluggable evidence bundles for ApprovalGate (§E.1).

QA diffs and precedent tasks do not exist yet. The key list is the extension
point — later phases add keys (and builders) without forking a new gate class.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel

from orchestration.state import SDLCState

# Always-on keys for this phase. Callers can add more via extra builders.
DEFAULT_EVIDENCE_KEYS: tuple[str, ...] = (
    "task_summary",
    "phase_artifact",
    "confidence_breakdown",
)

# Which SDLCState field is the "current phase artifact" for a checkpoint.
_CHECKPOINT_ARTIFACT: dict[str, str | None] = {
    "scope": "requirements",
    "design": "architecture",
    "security": "architecture",
    "release": "qa_evidence",
    "pr": "implementation_results",
    "deployment": "deployment_record",
}

EvidenceBuilder = Callable[[SDLCState], dict[str, Any]]


class EvidenceBundleSpec(BaseModel):
    """Named slices to include. Unknown names are filled by extra_builders."""

    include: tuple[str, ...] = DEFAULT_EVIDENCE_KEYS


def assemble_evidence_bundle(
    state: SDLCState,
    spec: EvidenceBundleSpec | None = None,
    *,
    checkpoint: str,
    extra_builders: Mapping[str, EvidenceBuilder] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Packet the human sees at an approval gate.

    Later phases add keys (diff, QA, past tasks) via extra_builders.
    Missing data stays null — we do not invent a fake QA report.
    """
    wanted = list((spec or EvidenceBundleSpec()).include)
    builders: dict[str, EvidenceBuilder] = {
        "task_summary": _task_summary,
        "phase_artifact": lambda s: _phase_artifact(s, checkpoint),
        "confidence_breakdown": _confidence_breakdown,
    }
    if extra_builders:
        builders.update(extra_builders)
    bundle: dict[str, Any] = {"checkpoint": checkpoint}
    for key in wanted:
        builder = builders.get(key)
        if builder is None:
            bundle[key] = None
            continue
        bundle[key] = builder(state)
    if extra:
        bundle.update(extra)
    return bundle


def _task_summary(state: SDLCState) -> dict[str, Any]:
    return {
        "task_id": state["task_id"],
        "workflow_profile_id": state.get("workflow_profile_id"),
        "intent_version": state.get("intent_version") or 0,
        "plan_version": state.get("plan_version") or 0,
    }


def _phase_artifact(state: SDLCState, checkpoint: str) -> Any:
    field = _CHECKPOINT_ARTIFACT.get(checkpoint)
    if field is None:
        return None
    return state.get(field)  # type: ignore[literal-required]


def _confidence_breakdown(state: SDLCState) -> dict[str, Any]:
    # Real Task.confidence_score is written in Section 05. Until then we only
    # show flags and spend so the human has *something* honest to look at.
    flags = list(state.get("validation_flags") or [])
    return {
        "validation_flag_count": len(flags),
        "flag_types": [flag.get("flag_type") for flag in flags],
        "phase_costs": dict(state.get("phase_costs") or {}),
        "total_cost_usd": state.get("total_cost_usd") or 0.0,
    }
