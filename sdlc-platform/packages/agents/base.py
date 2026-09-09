"""Shared scaffolding for every LLM-backed agent (`final_plan.md` §E.8).

Five concerns only: assemble context, route a model, invoke it, validate with
MASC, retry transients. Phase-specific writes go in `apply_output`, not here.
Does not import OpenTelemetry — spans go through TelemetrySink.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from common.budget import BudgetTracker
from common.task import Task, TaskBudget
from common.telemetry import TelemetrySink
from model_adapters.base import ChatMessage, ModelAdapter, ModelRequest, ModelResponse
from model_adapters.circuit_breaker import ProviderUnavailable
from model_adapters.router import ModelRouter
from model_adapters.telemetry import InstrumentedAdapter
from orchestration.masc import MASCEngine, MASCValidationError
from orchestration.state import SDLCState

SleepFn = Callable[[float], Awaitable[None]]

# Cap so a flaky node cannot sleep for minutes inside one graph step.
_BACKOFF_CAP_S = 8.0


class BaseAgent(ABC):
    """Template method: context → router → model → MASC → state.

    Subclasses set `agent_id`, `phase`, and `operation` (router keys) and
    implement `build_context` / `output_schema`. ApprovalGate (Section 02) is a
    node factory, not a subclass — it does not call a model.
    """

    agent_id: str
    phase: str
    operation: str

    def __init__(
        self,
        *,
        router: ModelRouter,
        masc: MASCEngine,
        sink: TelemetrySink,
        task: Task | None = None,
        max_retries: int | None = None,
        sleep: SleepFn | None = None,
        backoff_base_s: float = 0.5,
        tracker: BudgetTracker | None = None,
    ) -> None:
        self._router = router
        self._masc = masc
        self._sink = sink
        self._task = task
        # Optional: persist token/cost rows. Intake passes this; tests often skip it.
        self._tracker = tracker
        budget = task.budget if task is not None else TaskBudget()
        # max_retries_per_node = retries after the first try (default 3 → 4 attempts).
        self._max_retries = budget.max_retries_per_node if max_retries is None else max_retries
        self._sleep = sleep
        self._backoff_base_s = backoff_base_s
        self._masc.register_schema(self.agent_id, self.output_schema)

    @property
    @abstractmethod
    def output_schema(self) -> type[BaseModel]:
        """Pydantic schema MASC Check 1 validates. Section 03+ live under prompts/schemas/."""

    @abstractmethod
    def build_context(self, state: SDLCState) -> list[ChatMessage]:
        """Minimal prompt context. Progressive/budgeted assembly is Phase 12."""

    async def run(self, state: SDLCState) -> SDLCState:
        """Drive one agent turn. Raises MASCValidationError if output must not enter state."""
        last_error: BaseException | None = None
        attempts = self._max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                return await self._run_once(state, attempt)
            except MASCValidationError as exc:
                last_error = exc
                if not exc.retryable or attempt >= attempts:
                    raise
            except ProviderUnavailable:
                # Open circuit: pause the task (Section 03+ graph) — do not retry here.
                raise
            except Exception as exc:
                last_error = exc
                if attempt >= attempts:
                    raise
            await self._backoff(attempt)
        assert last_error is not None
        raise last_error

    def apply_output(self, state: SDLCState, output: BaseModel) -> SDLCState:
        """Default: audit event only. Planning Manager overrides to write Task fields."""
        event = {
            "event_id": uuid4().hex,
            "task_id": state["task_id"],
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_id": self.agent_id,
            "phase": self.phase,
            "span_id": None,
            "parent_span_id": None,
            "event_type": "agent_completed",
            "payload": output.model_dump(mode="json"),
        }
        return {**state, "agent_events": [*state["agent_events"], event]}

    @contextmanager
    def tool_span(
        self,
        name: str,
        *,
        task_id: str,
        parent_span_id: str | None = None,
    ) -> Iterator[str]:
        """Wrap a local tool body. Model tool_calls used only as structured output skip this."""
        with self._sink.span(
            kind="tool_call",
            name=name,
            task_id=task_id,
            phase=self.phase,
            agent_id=self.agent_id,
            parent_span_id=parent_span_id,
        ) as span_id:
            yield span_id

    async def _run_once(self, state: SDLCState, attempt: int) -> SDLCState:
        task_id = state["task_id"]
        with self._sink.span(
            kind="agent",
            name=self.agent_id,
            task_id=task_id,
            phase=self.phase,
            agent_id=self.agent_id,
            attributes={"attempt_number": attempt},
        ) as agent_span:
            adapter = self._instrument(self._select(), task_id)
            request = ModelRequest(
                messages=self.build_context(state),
                task_id=task_id,
                phase=self.phase,
                agent_id=self.agent_id,
                operation=self.operation,
                parent_span_id=agent_span,
            )
            response = await _complete(adapter, request)
            raw = self._parse(response)
            with self._sink.span(
                kind="validation",
                name="masc",
                task_id=task_id,
                phase=self.phase,
                agent_id=self.agent_id,
                parent_span_id=agent_span,
            ):
                ok, flag = self._masc.validate(raw, self.agent_id, self.phase, state)
                if not ok:
                    assert flag is not None
                    flagged: SDLCState = {
                        **state,
                        "validation_flags": [*state["validation_flags"], flag],
                    }
                    raise MASCValidationError(flag, flagged)
            parsed = self.output_schema.model_validate(raw)
            return self.apply_output(state, parsed)

    def _select(self) -> ModelAdapter:
        context: dict[str, Any] = {}
        if self._task is not None:
            context["risk_tier"] = self._task.risk_tier.value
        return self._router.select(self.phase, self.operation, context)

    def _instrument(self, adapter: ModelAdapter, task_id: str) -> ModelAdapter:
        # Wrap so llm_call spans nest under the agent span, and cost rows persist
        # when a BudgetTracker was passed in.
        if isinstance(adapter, InstrumentedAdapter):
            return adapter
        return InstrumentedAdapter(
            adapter,
            sink=self._sink,
            tracker=self._tracker,
            default_task_id=task_id,
            default_phase=self.phase,
            default_agent_id=self.agent_id,
        )

    def _parse(self, response: ModelResponse) -> dict[str, Any]:
        if response.tool_calls:
            return dict(response.tool_calls[0].arguments)
        content = (response.content or "").strip()
        try:
            loaded = json.loads(content)
        except json.JSONDecodeError:
            return {"_unparsed": content}
        if not isinstance(loaded, dict):
            return {"_unparsed": loaded}
        return loaded

    async def _backoff(self, failed_attempt: int) -> None:
        delay = min(self._backoff_base_s * (2 ** (failed_attempt - 1)), _BACKOFF_CAP_S)
        if self._sleep is None:
            await asyncio.sleep(delay)
            return
        await self._sleep(delay)


async def _complete(adapter: ModelAdapter, request: ModelRequest) -> ModelResponse:
    """Prefer acomplete so a BudgetTracker on InstrumentedAdapter can record cost."""
    acomplete = getattr(adapter, "acomplete", None)
    if callable(acomplete):
        return await acomplete(request)
    return adapter.complete(request)
