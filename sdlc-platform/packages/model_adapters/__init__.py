"""Public ModelAdapter surface. Does not import any provider SDK."""

from model_adapters.base import (
    ChatMessage,
    EmbeddingResult,
    ModelAdapter,
    ModelChunk,
    ModelPricing,
    ModelRequest,
    ModelResponse,
    TokenUsage,
    ToolCall,
    ToolSpec,
)
from model_adapters.circuit_breaker import CircuitBreaker, CircuitState, ProviderUnavailable
from model_adapters.registry import PricingRegistry, compute_cost, load_pricing_registry
from model_adapters.router import CAPABILITY_REQUIREMENTS, ModelRouter, NoCapableModelError
from model_adapters.telemetry import InstrumentedAdapter

__all__ = [
    "CAPABILITY_REQUIREMENTS",
    "ChatMessage",
    "CircuitBreaker",
    "CircuitState",
    "EmbeddingResult",
    "InstrumentedAdapter",
    "ModelAdapter",
    "ModelChunk",
    "ModelPricing",
    "ModelRequest",
    "ModelResponse",
    "ModelRouter",
    "NoCapableModelError",
    "PricingRegistry",
    "ProviderUnavailable",
    "TokenUsage",
    "ToolCall",
    "ToolSpec",
    "compute_cost",
    "load_pricing_registry",
]
