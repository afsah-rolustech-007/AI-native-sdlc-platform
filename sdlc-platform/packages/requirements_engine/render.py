"""Render engineer-facing question text. No LLM.

YAML `render` templates may include `{evidence}`. Missing templates fall back
to the generic `text` plus a bullet list of evidence refs.
"""

from __future__ import annotations

from requirements_engine.claims import EvidenceRecord
from requirements_engine.models import Question


def render_question(
    question: Question,
    evidence: list[EvidenceRecord] | None = None,
    extra_refs: list[str] | None = None,
) -> str:
    """Fill `{evidence}` or append refs. Never calls a model."""
    refs = _refs(evidence, extra_refs)
    evidence_block = _format_refs(refs)
    if question.render:
        if "{evidence}" in question.render:
            return question.render.replace("{evidence}", evidence_block)
        if refs:
            return f"{question.render}\n{evidence_block}"
        return question.render
    if refs:
        return f"{question.text}\n{evidence_block}"
    return question.text


def _refs(evidence: list[EvidenceRecord] | None, extra_refs: list[str] | None) -> list[str]:
    refs: list[str] = []
    for item in evidence or []:
        if item.unavailable:
            continue
        refs.extend(item.refs)
    refs.extend(extra_refs or [])
    seen: set[str] = set()
    out: list[str] = []
    for ref in refs:
        if not ref or ref in seen:
            continue
        seen.add(ref)
        out.append(ref)
    return out


def _format_refs(refs: list[str]) -> str:
    if not refs:
        return "(no repository evidence yet)"
    return "\n".join(f"- {ref}" for ref in refs)
