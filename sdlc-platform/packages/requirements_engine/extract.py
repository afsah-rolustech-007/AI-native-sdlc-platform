"""Repo-blind structured extraction: raw request → ClaimSet via ModelAdapter."""

from __future__ import annotations

import json
from typing import Any

from model_adapters.base import ChatMessage, ModelAdapter, ModelRequest, ModelResponse, ToolSpec
from requirements_engine.claims import (
    Claim,
    ClaimKind,
    ClaimSet,
    EpistemicStatus,
    Provenance,
)
from requirements_engine.exceptions import ExtractError

EXTRACT_CLAIMS_TOOL = ToolSpec(
    name="extract_claims",
    description=(
        "Record requirements claims found in the user's request text. "
        "Do not invent repository facts. Do not guess tech stack."
    ),
    parameters={
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "kind": {
                            "type": "string",
                            "enum": [kind.value for kind in ClaimKind],
                        },
                        "text": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["DECISION", "UNKNOWN", "CONTRADICTION"],
                        },
                        "nfr_type": {"type": "string"},
                        "touches_auth": {"type": "boolean"},
                        "touches_pii": {"type": "boolean"},
                        "touches_payments": {"type": "boolean"},
                        "has_database_changes": {"type": "boolean"},
                    },
                    "required": ["kind", "text"],
                },
            }
        },
        "required": ["claims"],
    },
)

_SYSTEM = (
    "You extract a structured ClaimSet from an engineering request. "
    "Use only the user message. Do not assume anything about a repository, "
    "architecture summary, files, symbols, or existing code. "
    "Explicit user requirements are DECISION. Vague or missing items are UNKNOWN. "
    "Never emit FACT or INFERENCE — those require repository evidence later. "
    "Call extract_claims exactly once."
)


def extract_claims(
    request: str,
    adapter: ModelAdapter,
    *,
    extra_intake: str | None = None,
) -> ClaimSet:
    """One structured ModelAdapter call. Repo-blind. Fail closed on parse failure."""
    user_text = request if not extra_intake else f"{request}\n\n{extra_intake}"
    messages = [
        ChatMessage(role="system", content=_SYSTEM),
        ChatMessage(role="user", content=user_text),
    ]
    model_request = ModelRequest(
        messages=messages,
        tools=[EXTRACT_CLAIMS_TOOL],
        temperature=0.0,
        phase="requirements",
        operation="extract_claims",
    )
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            response = adapter.call_tools(model_request, [EXTRACT_CLAIMS_TOOL])
            return _claimset_from_response(response, request)
        except ExtractError as exc:
            last_error = exc
        except Exception as exc:
            last_error = ExtractError(f"adapter failed: {exc}")
    _ = last_error
    return ClaimSet(claims=[], raw_request=request, extract_failed=True)


def _claimset_from_response(response: ModelResponse, request: str) -> ClaimSet:
    payload = _payload_from_response(response)
    raw_claims = payload.get("claims")
    if not isinstance(raw_claims, list):
        raise ExtractError("extract_claims result missing claims list")
    claims: list[Claim] = []
    for index, item in enumerate(raw_claims):
        if not isinstance(item, dict):
            raise ExtractError(f"claim {index} is not an object")
        claims.append(_claim_from_item(item, index))
    return ClaimSet(claims=claims, raw_request=request, extract_failed=False)


def _payload_from_response(response: ModelResponse) -> dict[str, Any]:
    for call in response.tool_calls:
        if call.name == EXTRACT_CLAIMS_TOOL.name:
            if not isinstance(call.arguments, dict):
                raise ExtractError("extract_claims arguments must be an object")
            return call.arguments
    if response.content:
        try:
            parsed = json.loads(response.content)
        except json.JSONDecodeError as exc:
            raise ExtractError("response content is not JSON") from exc
        if isinstance(parsed, dict):
            return parsed
    raise ExtractError("no extract_claims tool call in model response")


def _claim_from_item(item: dict[str, Any], index: int) -> Claim:
    if "kind" not in item or "text" not in item:
        raise ExtractError(f"claim {index} missing kind or text")
    try:
        kind = ClaimKind(item["kind"])
    except ValueError as exc:
        raise ExtractError(f"claim {index} has invalid kind {item['kind']!r}") from exc
    raw_status = item.get("status", "UNKNOWN")
    if raw_status in {"FACT", "INFERENCE"}:
        status = EpistemicStatus.UNKNOWN
    else:
        try:
            status = EpistemicStatus(raw_status)
        except ValueError as exc:
            raise ExtractError(f"claim {index} has invalid status {raw_status!r}") from exc
        if status not in {
            EpistemicStatus.DECISION,
            EpistemicStatus.UNKNOWN,
            EpistemicStatus.CONTRADICTION,
        }:
            status = EpistemicStatus.UNKNOWN
    text = item["text"]
    if not isinstance(text, str) or not text.strip():
        raise ExtractError(f"claim {index} has empty text")
    return Claim(
        id=str(item.get("id") or f"c{index + 1}"),
        kind=kind,
        text=text.strip(),
        status=status,
        provenance=Provenance(source="request", ref=str(item.get("id") or f"c{index + 1}")),
        nfr_type=item.get("nfr_type"),
        touches_auth=item.get("touches_auth"),
        touches_pii=item.get("touches_pii"),
        touches_payments=item.get("touches_payments"),
        has_database_changes=item.get("has_database_changes"),
    )
