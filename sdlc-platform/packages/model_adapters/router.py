"""Capability-lookup router (`final_plan.md` §I.2).

Cheapest registered adapter whose score meets the table. No escalate_model_tier
(that is Phase 10). High-risk tasks bump the required score by 1 (still lookup,
not rejection-count escalation).
"""

from __future__ import annotations

from model_adapters.base import ModelAdapter
from model_adapters.circuit_breaker import CircuitBreaker

# Copied from §I.2. A Python constant is enough until Phase 15 has empirical data.
CAPABILITY_REQUIREMENTS: dict[tuple[str, str], int] = {
    ("requirements", "ambiguity_detection"): 8,
    ("design", "architecture"): 9,
    ("design", "security_analysis"): 8,
    ("design", "self_critique"): 8,
    ("implementation", "code_generation"): 6,
    ("implementation", "complex_refactor"): 8,
    ("implementation", "feedback_synthesis"): 9,
    ("qa", "spec_validation"): 7,
    ("qa", "static_analysis"): 1,
    ("any", "summarization"): 3,
    ("any", "intent_classification"): 4,
    ("masc", "semantic_drift"): 4,
}

_HIGH_RISK = frozenset({"high", "critical"})


class NoCapableModelError(LookupError):
    """Fail-closed: never return an under-capable model."""


def required_score(phase: str, operation: str, context: dict | None = None) -> int:
    table = CAPABILITY_REQUIREMENTS
    if (phase, operation) in table:
        required = table[(phase, operation)]
    elif ("any", operation) in table:
        required = table[("any", operation)]
    else:
        raise NoCapableModelError(f"no capability requirement for ({phase!r}, {operation!r})")
    risk = str((context or {}).get("risk_tier") or "").lower()
    if risk in _HIGH_RISK:
        required = min(10, required + 1)
    return required


def _unit_cost(adapter: ModelAdapter) -> float:
    pricing = adapter.pricing
    return pricing.input_price_per_1m + pricing.output_price_per_1m


class ModelRouter:
    def __init__(
        self,
        adapters: list[ModelAdapter],
        *,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        if not adapters:
            raise ValueError("ModelRouter needs at least one registered adapter")
        self._adapters = list(adapters)
        self._breaker = breaker

    def select(self, phase: str, operation: str, context: dict | None = None) -> ModelAdapter:
        needed = required_score(phase, operation, context)
        capable = [adapter for adapter in self._adapters if adapter.capability_score >= needed]
        if not capable:
            raise NoCapableModelError(
                f"no registered adapter meets score {needed} for ({phase}, {operation})"
            )
        chosen = min(capable, key=_unit_cost)
        if self._breaker is not None:
            return self._breaker.protect(chosen)
        return chosen
