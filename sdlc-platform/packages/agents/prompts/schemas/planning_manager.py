"""JSON the Planning Manager must return. MASC Check 1 validates this.

If the model omits a field or uses a fake work_type, the output is rejected
and never written to Task / SDLCState.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from common.task import RiskTier, WorkType


class PlanningManagerOutput(BaseModel):
    """Classified work. `confidence` is required so MASC Check 2 can run.

    Intake is not in the phase-floor table, so MASC uses the default 0.80 floor.
    """

    work_type: WorkType
    risk_tier: RiskTier
    rationale: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
