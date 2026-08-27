"""Eight no-op phase stubs. Each only writes its own placeholder artifact.

Task.state persistence and TelemetrySink spans live in `telemetry_adapter.py`
(the node wrapper, §D.2.1 / §B.8.5). Nodes must not import OpenTelemetry.

`design_node` calls LangGraph `interrupt()` (pause primitive). That is not a
`HITLRequest` row and does not write `hitl_log`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from orchestration.hitl import interrupt_for_design_approval
from orchestration.state import SDLCState

StubNode = Callable[[SDLCState], dict]


def intake_node(state: SDLCState) -> dict:
    return {
        "intent_version": 1,
        "intent_last_updated": datetime.now(UTC),
    }


def requirements_node(state: SDLCState) -> dict:
    return {
        "requirements": {
            "functional": ["stub: capture the request"],
            "non_functional": {},
            "acceptance_criteria": ["stub: graph reached requirements"],
            "open_ambiguities": [],
            "assumptions": [],
            "out_of_scope": [],
            "version": 1,
            "approved_at": None,
            "approved_by": None,
        }
    }


def design_node(state: SDLCState) -> dict:
    # interrupt() pauses; Command(resume=...) returns the decision and re-runs this node.
    decision = interrupt_for_design_approval(state["task_id"])
    approved = decision.lower() == "approve"
    return {
        "architecture": {
            "component_boundaries": [],
            "api_contracts": [],
            "database_design": {},
            "security_design": {},
            "deployment_strategy": "stub" if approved else "rejected-stub",
            "adr_ids": [],
            "version": 1,
            "approved_at": None,
        },
        # Observational only — proves resume values are used, not ignored.
        "agent_events": [
            {
                "event_id": uuid4().hex,
                "task_id": state["task_id"],
                "timestamp": datetime.now(UTC).isoformat(),
                "agent_id": "stub:design",
                "phase": "design",
                "span_id": None,
                "parent_span_id": None,
                "event_type": "hitl_responded",
                "payload": {"decision": decision},
            }
        ],
    }


def implementation_node(state: SDLCState) -> dict:
    return {
        "task_decomposition": {
            "tasks": [
                {
                    "id": "stub-1",
                    "description": "stub implementation",
                    "module": "app",
                    "target_files": [],
                    "declared_dependencies": [],
                    "model_tier_hint": "default",
                }
            ],
            "ownership_map": {},
            "version": 1,
        },
        "implementation_results": [
            {
                "subtask_id": "stub-1",
                "worker_id": "stub",
                "attempt_number": 1,
                "plan_version": 0,
                "wave_index": 0,
                "diff_ref": "blackboard://stub",
                "touches_files": [],
                "status": "validated",
            }
        ],
    }


def qa_node(state: SDLCState) -> dict:
    return {
        "qa_evidence": {
            "static_analysis": None,
            "security_findings": [],
            "mutation_score": None,
            "property_violations": [],
            "exploratory_findings": [],
            "spec_compliance": {},
            "coverage_delta": None,
            "risk_score": 0.0,
            "recommendation": "pass",
        }
    }


def review_node(state: SDLCState) -> dict:
    return {
        "validation_flags": [
            {
                "source": "stub",
                "agent_id": "stub-review",
                "phase": "review",
                "flag_type": "spec_inconsistency",
                "severity": "info",
                "detail": "stub review placeholder",
                "rollback_to": None,
            }
        ]
    }


def release_node(state: SDLCState) -> dict:
    return {
        "deployment_record": {
            "strategy": "rolling",
            "target_env": "stub",
            "pipeline_run_id": None,
            "canary_metrics": None,
            "health_status": None,
            "rollback_triggered": False,
            "deployed_at": None,
        }
    }


def monitoring_node(state: SDLCState) -> dict:
    # No dedicated monitoring artifact on SDLCState. Adapter marks TaskState.DONE after this.
    return {}


STUB_NODES: dict[str, StubNode] = {
    "intake": intake_node,
    "requirements": requirements_node,
    "design": design_node,
    "implementation": implementation_node,
    "qa": qa_node,
    "review": review_node,
    "release": release_node,
    "monitoring": monitoring_node,
}
