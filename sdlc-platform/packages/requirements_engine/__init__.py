"""Phase 04 requirements engine.

Group A: contracts/policy. Group B: snapshot + targeted RI (public door only).
Group C: classify / auto-answer / rank — no LLM, no RI calls.
Group D: trace, sufficiency, standalone session loop. No LangGraph.
"""

from requirements_engine.auto_answer import try_answer
from requirements_engine.claims import (
    Claim,
    ClaimKind,
    ClaimSet,
    EpistemicStatus,
    EvidenceRecord,
    Provenance,
    flag_contradiction,
    has_contradiction,
    is_fact_plus_decision,
)
from requirements_engine.classify import classify_claims
from requirements_engine.context import WorkflowContext
from requirements_engine.dag import QuestionQueue
from requirements_engine.decide import DecisionReport, SlotDecision, evaluate_slots
from requirements_engine.engine import EngineStepResult, RequirementsEngine
from requirements_engine.exceptions import (
    CycleError,
    EvidencePlanError,
    ExtractError,
    PredicateError,
    QuestionBankError,
    RequirementsEngineError,
    RetrievalError,
    SnapshotError,
)
from requirements_engine.extract import extract_claims
from requirements_engine.models import AutoAnswer, Question, SessionEvent, SessionEventKind
from requirements_engine.plans import EvidencePlan, parse_evidence_plan
from requirements_engine.project import RequirementsSpec, project_spec
from requirements_engine.question_bank import default_bank_path, load_question_bank
from requirements_engine.rank import RankConfig, rank_questions
from requirements_engine.retrieve import RetrievalSession, execute_plan
from requirements_engine.snapshot import SessionRepoSnapshot, SnapshotCache, build_snapshot
from requirements_engine.sufficiency import SufficiencyReport, evaluate_sufficiency
from requirements_engine.trace import SessionCounters, SessionTrace

__all__ = [
    "AutoAnswer",
    "Claim",
    "ClaimKind",
    "ClaimSet",
    "CycleError",
    "DecisionReport",
    "EngineStepResult",
    "EpistemicStatus",
    "EvidencePlan",
    "EvidencePlanError",
    "EvidenceRecord",
    "ExtractError",
    "PredicateError",
    "Provenance",
    "Question",
    "QuestionBankError",
    "QuestionQueue",
    "RankConfig",
    "RequirementsEngine",
    "RequirementsEngineError",
    "RequirementsSpec",
    "RetrievalError",
    "RetrievalSession",
    "SessionCounters",
    "SessionEvent",
    "SessionEventKind",
    "SessionRepoSnapshot",
    "SessionTrace",
    "SlotDecision",
    "SnapshotCache",
    "SnapshotError",
    "SufficiencyReport",
    "WorkflowContext",
    "build_snapshot",
    "classify_claims",
    "default_bank_path",
    "evaluate_slots",
    "evaluate_sufficiency",
    "execute_plan",
    "extract_claims",
    "flag_contradiction",
    "has_contradiction",
    "is_fact_plus_decision",
    "load_question_bank",
    "parse_evidence_plan",
    "project_spec",
    "rank_questions",
    "try_answer",
]
