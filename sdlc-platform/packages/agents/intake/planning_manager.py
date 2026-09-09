"""First real LLM agent: turn a raw request into work_type + risk_tier.

Does not write requirements. Does not pause for HITL. That is later sections.

Router keys: phase=`intake`, operation=`classification` → cheapest model that
meets score 4 (Fast tier / glm-4.7-flash).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from agents.base import BaseAgent
from agents.prompts.planning_manager import SYSTEM_PROMPT
from agents.prompts.schemas.planning_manager import PlanningManagerOutput
from model_adapters.base import ChatMessage
from orchestration.state import SDLCState

UNAVAILABLE_SUMMARY = (
    "Architecture summary unavailable (repository not indexed or index is stale). "
    "Do not invent repository facts."
)


class PlanningManager(BaseAgent):
    # These three strings are how ModelRouter picks a model.
    agent_id = "planning_manager"
    phase = "intake"
    operation = "classification"

    def __init__(
        self,
        *,
        request_text: str = "",
        architecture_summary: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._request_text = request_text
        self._architecture_summary = architecture_summary.strip() or UNAVAILABLE_SUMMARY

    @property
    def output_schema(self) -> type[BaseModel]:
        return PlanningManagerOutput

    def build_context(self, state: SDLCState) -> list[ChatMessage]:
        # Order matches §M.2: role/instructions, then the request, then L0 repo summary.
        request = self._request_text or last_user_text(state) or "(empty request)"
        return [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=f"Request:\n{request}"),
            ChatMessage(
                role="user",
                content=f"Architecture summary (Level 0):\n{self._architecture_summary}",
            ),
        ]

    def apply_output(self, state: SDLCState, output: BaseModel) -> SDLCState:
        # Parent writes an agent_completed audit event. We also bump intent_version
        # so later phases know intake actually classified something.
        updated = super().apply_output(state, output)
        return {
            **updated,
            "intent_version": max(int(updated.get("intent_version") or 0), 1),
            "intent_last_updated": datetime.now(UTC),
        }


def last_user_text(state: SDLCState) -> str:
    """Newest human message. LangGraph may store a dict or a Message object."""
    for message in reversed(list(state.get("messages") or [])):
        content = _message_content(message)
        if content:
            return content
    return ""


def _message_content(message: object) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "").strip()
    content = getattr(message, "content", None)
    return str(content or "").strip()
