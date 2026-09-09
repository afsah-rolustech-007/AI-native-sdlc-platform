"""MASC post-node middleware (`final_plan.md` §E.6).

Cheapest check first: schema (no tokens), then the §B.4 phase floor (no tokens),
then semantic drift (stubbed until Phase 06). Never imports OpenTelemetry.

If a check itself throws, that is not a pass — Fail-Closed routes to a human.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ValidationError

from orchestration.state import SDLCState, ValidationFlag

FlagType = Literal[
    "schema_violation",
    "semantic_drift",
    "confidence_below_threshold",
    "tool_error",
    "spec_inconsistency",
    "design_gap",
    "security_finding",
]
Severity = Literal["info", "warning", "error", "critical"]

# Exact §E.6 / §B.4 floors. Unknown phases use 0.80 (the requirements floor).
CONFIDENCE_THRESHOLDS: dict[str, float] = {
    "requirements": 0.80,
    "design": 0.85,
    "implementation": 0.75,
    "qa": 0.90,
    "deployment": 0.95,
}

HIGH_STAKES_PHASES: frozenset[str] = frozenset(
    {"design", "implementation_plan", "deployment"}
)

DriftVerdict = Literal["not checked"]


class MASCValidationError(Exception):
    """MASC rejected the output. The artifact must not enter SDLCState."""

    def __init__(self, flag: ValidationFlag, state: SDLCState | None = None) -> None:
        self.flag = flag
        self.state = state
        super().__init__(flag["detail"])

    @property
    def retryable(self) -> bool:
        """Schema misses can be a flaky model; confidence/internal errors must not retry."""
        return self.flag["flag_type"] == "schema_violation"


class MASCEngine:
    """Post-node output validator. Register each agent's Pydantic schema by agent_id."""

    CONFIDENCE_THRESHOLDS = CONFIDENCE_THRESHOLDS
    HIGH_STAKES_PHASES = HIGH_STAKES_PHASES

    def __init__(self, schemas: dict[str, type[BaseModel]] | None = None) -> None:
        self._schemas: dict[str, type[BaseModel]] = dict(schemas or {})

    def register_schema(self, agent_id: str, schema: type[BaseModel]) -> None:
        self._schemas[agent_id] = schema

    def validate(
        self,
        output: dict,
        agent_id: str,
        phase: str,
        state: SDLCState,
    ) -> tuple[bool, ValidationFlag | None]:
        """Run Checks 1–3. Always returns a tuple — never raises to the caller."""
        try:
            return self._validate_inner(output, agent_id, phase, state)
        except Exception as exc:
            # Bug in a check: never treat that as a pass.
            return False, _flag(
                agent_id,
                phase,
                flag_type="tool_error",
                severity="error",
                detail=f"MASC internal error: {type(exc).__name__}: {exc}",
            )

    def check_semantic_drift(
        self,
        output: dict,
        requirements: object,
        intent_version: int,
    ) -> DriftVerdict:
        """Check 3. Phase 06 implements the real comparison against the spec."""
        return "not checked"

    def _validate_inner(
        self,
        output: dict,
        agent_id: str,
        phase: str,
        state: SDLCState,
    ) -> tuple[bool, ValidationFlag | None]:
        if not self._validate_schema(output, agent_id):
            return False, _flag(
                agent_id,
                phase,
                flag_type="schema_violation",
                severity="error",
                detail=f"output failed schema for agent {agent_id!r}",
            )

        floor = self.CONFIDENCE_THRESHOLDS.get(phase, 0.80)
        confidence = output.get("confidence", 1.0)
        if not _is_unit_interval(confidence) or float(confidence) < floor:
            return False, _flag(
                agent_id,
                phase,
                flag_type="confidence_below_threshold",
                severity="warning",
                detail=f"declared confidence {confidence!r} is below floor {floor} for phase {phase!r}",
            )

        if phase in self.HIGH_STAKES_PHASES:
            verdict = self.check_semantic_drift(
                output,
                state.get("requirements"),
                int(state.get("intent_version") or 0),
            )
            if verdict != "not checked":
                return False, _flag(
                    agent_id,
                    phase,
                    flag_type="semantic_drift",
                    severity="error",
                    detail="semantic drift detected",
                )

        return True, None

    def _validate_schema(self, output: dict, agent_id: str) -> bool:
        schema = self._schemas.get(agent_id)
        if schema is None:
            return False
        try:
            schema.model_validate(output)
        except ValidationError:
            return False
        return True


def _is_unit_interval(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return 0.0 <= float(value) <= 1.0


def _flag(
    agent_id: str,
    phase: str,
    *,
    flag_type: FlagType,
    severity: Severity,
    detail: str,
) -> ValidationFlag:
    return {
        "source": "masc",
        "agent_id": agent_id,
        "phase": phase,
        "flag_type": flag_type,
        "severity": severity,
        "detail": detail,
        "rollback_to": None,
    }
