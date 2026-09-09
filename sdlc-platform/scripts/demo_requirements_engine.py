"""Phase 04 Group D checkpoint: standalone requirements engine. No LangGraph.

  uv run python scripts/demo_requirements_engine.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.helpers.fake_repo_intel import FakeRI
from tests.unit.test_extract import RecordingAdapter

from common.task import WorkType
from requirements_engine.context import WorkflowContext
from requirements_engine.engine import RequirementsEngine
from requirements_engine.rank import RankConfig
from requirements_engine.snapshot import SnapshotCache

WELL_SPEC = {
    "claims": [
        {
            "id": "c1",
            "kind": "objective",
            "text": "Add invoice CSV export for billing admins",
            "status": "DECISION",
        },
        {
            "id": "c2",
            "kind": "functional",
            "text": "Billing admins are the consumers of this change",
            "status": "DECISION",
        },
        {
            "id": "c3",
            "kind": "acceptance",
            "text": "Given an invoice, a CSV downloads with id and amount",
            "status": "DECISION",
        },
    ]
}
VAGUE = {
    "claims": [
        {
            "id": "c1",
            "kind": "unknown",
            "text": "add auth",
            "status": "UNKNOWN",
            "touches_auth": True,
        }
    ]
}
SECURITY = {
    "claims": [
        {
            "id": "c1",
            "kind": "objective",
            "text": "Add login with the existing auth module",
            "status": "DECISION",
            "touches_auth": True,
        },
        {
            "id": "c2",
            "kind": "functional",
            "text": "End users are the consumers of this change",
            "status": "DECISION",
        },
        {
            "id": "c3",
            "kind": "acceptance",
            "text": "Given a valid password, login succeeds",
            "status": "DECISION",
        },
    ]
}
CONTRADICTION = {
    "claims": [
        {"id": "a", "kind": "functional", "text": "REST only", "status": "DECISION"},
        {"id": "b", "kind": "functional", "text": "GraphQL only", "status": "DECISION"},
    ]
}


def _print(title: str, result: Any, engine: RequirementsEngine) -> None:
    counters = result.counters.model_dump()
    print(f"\n=== {title} ===")
    print(f"outcome: {result.action}")
    print(f"reason: {result.reason}")
    print(
        "counters: "
        f"llm={counters['llm_calls']} ri={counters['ri_calls']} "
        f"cache={counters['ri_cache_hits']} human={counters['human_questions']} "
        f"auto={counters['auto_answers']} budget={counters['session_budget_consumed']}"
    )
    if result.auto_answers:
        print("AUTO:")
        for item in result.auto_answers:
            print(f"  {item.slot_id}: {item.answer}")
    asked = [event.payload.get("question_id") for event in engine.trace.of_kind("ask")]
    if asked:
        print(f"ASK (one per step): {asked}")
    if result.question_id:
        print(f"pending: {result.question_id}")
    if result.spec is not None:
        print("RequirementsSpec:")
        print(json.dumps(result.spec, default=str, indent=2)[:1200])
    print(f"trace kinds: {engine.trace.kinds()}")


async def _run_named(name: str) -> None:
    cache = SnapshotCache()
    if name == "well_specified":
        engine = RequirementsEngine(
            "Add invoice CSV export for billing admins",
            RecordingAdapter(arguments=WELL_SPEC),
            FakeRI(),
            context=WorkflowContext(
                work_type=WorkType.FEATURE,
                touches_auth=False,
                touches_pii=False,
                touches_payments=False,
                has_database_changes=False,
            ),
            snapshot_cache=cache,
        )
        result = await engine.run()
        _print("1. Well specified → spec_ready", result, engine)
        return
    if name == "vague":
        engine = RequirementsEngine(
            "add auth",
            RecordingAdapter(arguments=VAGUE),
            FakeRI(),
            snapshot_cache=cache,
            rank_config=RankConfig(human_question_budget=12),
        )
        result = await engine.run(
            {
                "Q1": "Add SSO for employees",
                "Q2": "Internal employees",
                "Q3": "Employee can sign in with SSO",
                "Qsec1": "SOC2",
                "Qsec2": "confidential",
                "Qsec3": "none",
            }
        )
        _print("2. Vague request → scripted answers", result, engine)
        return
    if name == "security":
        engine = RequirementsEngine(
            "Add login with the existing auth module",
            RecordingAdapter(arguments=SECURITY),
            FakeRI(),
            context=WorkflowContext(touches_auth=True),
            snapshot_cache=cache,
        )
        result = await engine.run()
        _print("3. Security-sensitive → Qsec remains", result, engine)
        return
    if name == "contradiction":
        engine = RequirementsEngine(
            "Use REST only. Also use GraphQL only.",
            RecordingAdapter(arguments=CONTRADICTION),
            FakeRI(),
            context=WorkflowContext(
                touches_auth=False, touches_pii=False, touches_payments=False
            ),
            snapshot_cache=cache,
        )
        result = await engine.run()
        _print("4. Contradiction → needs_hitl", result, engine)
        return
    if name == "stale":
        engine = RequirementsEngine(
            "Add invoice CSV export",
            RecordingAdapter(arguments=WELL_SPEC),
            FakeRI(state="stale", stale_paths=["touched.py"]),
            context=WorkflowContext(
                touches_auth=False, touches_pii=False, touches_payments=False
            ),
            snapshot_cache=cache,
        )
        result = await engine.run()
        _print("5. Stale repository → needs_hitl", result, engine)
        return
    raise SystemExit(f"unknown scenario {name}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        choices=["well_specified", "vague", "security", "contradiction", "stale", "all"],
        default="all",
    )
    args = parser.parse_args()
    names = (
        ["well_specified", "vague", "security", "contradiction", "stale"]
        if args.scenario == "all"
        else [args.scenario]
    )
    for name in names:
        await _run_named(name)


if __name__ == "__main__":
    asyncio.run(main())
