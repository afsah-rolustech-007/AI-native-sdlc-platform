"""EvidencePlan: what to retrieve, with which RI signal, within what budget.

Plans live in question-bank YAML. Routing is need-driven (the method list), not
a global retrieval ladder. This module only validates. Execution is retrieve.py.
Extractors named here are presence checks used to stop fetching — they do not
auto-answer (Group C).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from requirements_engine.exceptions import EvidencePlanError

SignalName = Literal["snapshot", "manifest", "symbol", "lexical", "graph", "semantic"]
GraphOp = Literal["callers", "callees", "dependencies", "dependents", "impact"]
AcceptAs = Literal["fact", "inference"]
OnInsufficient = Literal["ask_human", "unknown"]

# Names used as Group B stop-checks and Group C typed extractors.
KNOWN_EXTRACTORS: frozenset[str] = frozenset(
    {
        "service_exists",
        "database_entities_present",
        "symbol_exists",
        "identifier_in_snippet",
        "neighborhood_nonempty",
        "dependency_declared",
        "languages_from_snapshot",
        "declared_database",
    }
)
KNOWN_SIGNALS: frozenset[str] = frozenset(
    {"snapshot", "manifest", "symbol", "lexical", "graph", "semantic"}
)
RI_SIGNALS: frozenset[str] = frozenset({"symbol", "lexical", "graph", "semantic"})


class PlanMethod(BaseModel):
    """One retrieval step. Later steps run only if this one does not accept."""

    model_config = ConfigDict(extra="forbid")

    signal: SignalName
    query: str | None = None
    query_from_claims: str | None = None
    symbol_id: str | None = None
    symbol_id_from: str | None = None
    file_path: str | None = None
    paths_from_snapshot: bool = False
    top_k: int | None = None
    min_score: float | None = None
    depth: int | None = None
    extractor: str | None = None
    budget: int = 1
    graph_op: GraphOp | None = None

    @model_validator(mode="after")
    def check_method(self) -> PlanMethod:
        if self.extractor is not None and self.extractor not in KNOWN_EXTRACTORS:
            raise ValueError(f"unknown extractor {self.extractor!r}")
        if self.budget < 0:
            raise ValueError("budget must be >= 0")
        if self.top_k is not None and self.top_k < 1:
            raise ValueError("top_k must be >= 1")
        if self.signal == "graph" and self.graph_op is None:
            # Prefer an explicit op; fall back so a file path still does something.
            if self.file_path:
                self.graph_op = "dependents"
            elif self.symbol_id or self.symbol_id_from:
                self.graph_op = "callers"
            else:
                self.graph_op = "impact"
        return self


class EvidencePlan(BaseModel):
    """Per-slot retrieval policy. Semantic-only plans cannot claim FACT."""

    model_config = ConfigDict(extra="forbid")

    need: str
    methods: list[PlanMethod] = Field(default_factory=list)
    accept_as: AcceptAs = "fact"
    on_insufficient: OnInsufficient = "unknown"
    max_ri_calls: int = 4

    @model_validator(mode="after")
    def check_plan(self) -> EvidencePlan:
        if not self.need.strip():
            raise ValueError("need is required")
        if self.max_ri_calls < 0:
            raise ValueError("max_ri_calls must be >= 0")
        if not self.methods:
            self.methods = default_methods_for_need(self.need)
        if (
            self.accept_as == "fact"
            and self.methods
            and all(method.signal == "semantic" for method in self.methods)
        ):
            raise ValueError("semantic-only plans cannot accept_as fact")
        return self


def parse_evidence_plan(raw: dict[str, Any]) -> EvidencePlan:
    """Validate YAML/JSON. Unknown signals fail here, at load time."""
    if not isinstance(raw, dict):
        raise EvidencePlanError("evidence_plan must be a mapping")
    methods = raw.get("methods")
    if isinstance(methods, list):
        for index, method in enumerate(methods):
            if isinstance(method, dict) and "signal" in method:
                signal = method["signal"]
                if signal not in KNOWN_SIGNALS:
                    raise EvidencePlanError(f"unknown signal {signal!r} at methods[{index}]")
    try:
        return EvidencePlan.model_validate(raw)
    except ValidationError as exc:
        raise EvidencePlanError(str(exc)) from exc


def default_methods_for_need(need: str) -> list[PlanMethod]:
    """Cost preference used only when YAML omitted `methods` (it should not)."""
    text = need.lower()
    if any(token in text for token in ("jwt", "identifier", "references", "used")):
        return [PlanMethod(signal="lexical"), PlanMethod(signal="graph")]
    if any(token in text for token in ("impact", "blast", "depend")):
        return [PlanMethod(signal="graph", graph_op="impact")]
    if any(token in text for token in ("related", "semantic", "about")):
        return [PlanMethod(signal="snapshot"), PlanMethod(signal="semantic")]
    if any(token in text for token in ("symbol", "signature")):
        return [PlanMethod(signal="symbol"), PlanMethod(signal="lexical")]
    if any(token in text for token in ("fastapi", "django", "dependency", "package")):
        return [PlanMethod(signal="manifest"), PlanMethod(signal="snapshot")]
    return [PlanMethod(signal="snapshot"), PlanMethod(signal="manifest")]
