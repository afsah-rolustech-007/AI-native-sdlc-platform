from model_adapters.base import ModelAdapter, ModelRequest, ModelResponse


class Incomplete:
    """Deliberately missing stream/call_tools/embed/pricing/capability_score."""

    def complete(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError


def _assigned() -> ModelAdapter:
    return Incomplete()
