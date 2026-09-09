"""Standalone requirements-engine session loop. No LangGraph. No HITL interrupt.

One structured LLM extract. Snapshot once. Targeted RI. Deterministic
classify / auto-answer / rank. One human question per `step()`. Exit via
RequirementsSufficiency — never via the §B.4 confidence formula.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from model_adapters.base import ModelAdapter
from repo_intel.exceptions import StaleIndexError
from requirements_engine.claims import (
    Claim,
    ClaimKind,
    ClaimSet,
    EpistemicStatus,
    EvidenceRecord,
    Provenance,
)
from requirements_engine.classify import classify_claims
from requirements_engine.context import WorkflowContext
from requirements_engine.dag import QuestionQueue
from requirements_engine.decide import SlotDecision, evaluate_slots
from requirements_engine.exceptions import SnapshotError
from requirements_engine.extract import extract_claims
from requirements_engine.models import AutoAnswer, Question, SessionEventKind
from requirements_engine.plans import parse_evidence_plan
from requirements_engine.project import RequirementsSpec, project_spec
from requirements_engine.question_bank import default_bank_path, load_question_bank
from requirements_engine.rank import RankConfig
from requirements_engine.retrieve import RetrievalSession, execute_plan
from requirements_engine.ri_client import RepoIntelClient
from requirements_engine.seed import seed_slots_from_decisions
from requirements_engine.snapshot import SessionRepoSnapshot, SnapshotCache, build_snapshot
from requirements_engine.sufficiency import SufficiencyReport, evaluate_sufficiency
from requirements_engine.trace import SessionCounters, SessionTrace

EngineAction = Literal["ask", "spec_ready", "accept_gaps", "needs_hitl"]

_MAX_INNER = 32
_MAX_RUN_STEPS = 24

_CATEGORY_KIND = {
    "business_objective": ClaimKind.OBJECTIVE,
    "performance": ClaimKind.NFR,
    "scalability": ClaimKind.NFR,
    "reliability": ClaimKind.NFR,
    "security_compliance": ClaimKind.CONSTRAINT,
}


class EngineStepResult(BaseModel):
    """Caller-facing step: ASK one question, or a terminal 3-way exit."""

    action: EngineAction
    reason: str
    question_id: str | None = None
    question_text: str | None = None
    mandatory: bool = False
    spec: RequirementsSpec | None = None
    sufficiency: SufficiencyReport | None = None
    auto_answers: list[AutoAnswer] = Field(default_factory=list)
    counters: SessionCounters = Field(default_factory=SessionCounters)


class RequirementsEngine:
    """One session. `step()` never dumps a question list. `run()` is bounded."""

    def __init__(
        self,
        request: str,
        adapter: ModelAdapter,
        ri: RepoIntelClient,
        *,
        context: WorkflowContext | None = None,
        rank_config: RankConfig | None = None,
        snapshot_cache: SnapshotCache | None = None,
        questions: list[Question] | None = None,
        extra_intake: str | None = None,
    ) -> None:
        bank = questions if questions is not None else load_question_bank(default_bank_path())
        self.request = request
        self._adapter = adapter
        self._ri = ri
        self._extra_intake = extra_intake
        self._rank_config = rank_config or RankConfig()
        self._cache = snapshot_cache if snapshot_cache is not None else SnapshotCache()
        self.queue = QuestionQueue(bank, context or WorkflowContext())
        self.claims = ClaimSet(raw_request=request)
        self.evidence: list[EvidenceRecord] = []
        self.snapshot: SessionRepoSnapshot | None = None
        self.trace = SessionTrace()
        self._session: RetrievalSession | None = None
        self._bootstrapped = False
        self._accept_gaps = False
        self._ri_unavailable = False
        self._ri_unavailable_reason: str | None = None
        self._snapshot_ri = 0
        self._retrieved: set[str] = set()
        self._pending: SlotDecision | None = None
        self._terminal: EngineStepResult | None = None

    def accept_gaps(self) -> None:
        """Engineer explicitly accepts remaining open assumptions."""
        self._accept_gaps = True
        self._pending = None

    def answer(
        self,
        text: str,
        *,
        question_id: str | None = None,
        context_updates: dict[str, object] | None = None,
    ) -> None:
        """Record one engineer DECISION. Does not overwrite prior DECISIONs."""
        if self._terminal is not None:
            raise RuntimeError("session already exited")
        pending_id = self._pending.question_id if self._pending is not None else None
        qid = question_id or pending_id
        if qid is None:
            raise RuntimeError("no pending question to answer")
        question = self.queue.get(qid)
        self.queue.answer(
            qid,
            text,
            context_updates=context_updates,  # type: ignore[arg-type]
            source="human",
        )
        self.claims = _append_claim(self.claims, question, text)
        self.queue.apply_claims(self.claims)
        classified = classify_claims(self.claims, self.evidence, self.snapshot)
        self.claims = classified.claim_set
        self.trace.counters.human_questions += 1
        self.trace.append(
            SessionEventKind.ANSWER,
            question_id=qid,
            text=text,
            source="engineer",
        )
        self._pending = None

    async def step(self) -> EngineStepResult:
        """Evaluate once. Retrieve what is due. AUTO what is safe. ASK one slot."""
        if self._terminal is not None:
            return self._terminal
        if self._pending is not None:
            return _ask_result(self._pending, self.trace.counters)
        if not self._bootstrapped:
            await self._bootstrap()
        autos = await self._retrieve_and_auto()
        gate = self._sufficiency()
        self.trace.append(
            SessionEventKind.SUFFICIENCY,
            decision=gate.decision,
            reason=gate.reason,
            mandatory_unanswered=gate.mandatory_unanswered,
            evidence_coverage=gate.evidence_coverage,
        )
        if gate.decision != "continue":
            return self._exit(gate, autos)
        asked = self._ask_one(autos)
        if asked is not None:
            return asked
        gate = self._sufficiency()
        if gate.decision == "continue":
            gate = gate.model_copy(
                update={
                    "decision": "needs_hitl",
                    "reason": "no askable slot remains; cannot raise sufficiency further",
                }
            )
        return self._exit(gate, autos)

    async def run(
        self,
        answers: dict[str, str] | None = None,
        *,
        max_steps: int = _MAX_RUN_STEPS,
    ) -> EngineStepResult:
        """Drive `step()` until a terminal exit or a question without a scripted answer."""
        scripted = answers or {}
        for _ in range(max_steps):
            result = await self.step()
            if result.action != "ask":
                return result
            assert result.question_id is not None
            if result.question_id not in scripted:
                return result
            self.answer(scripted[result.question_id])
        return self._exit(
            evaluate_sufficiency(
                claim_set=self.claims,
                mandatory_unanswered=self._mandatory_unanswered(),
                askable_remaining=[],
                evidence_coverage=self._evidence_coverage(),
                human_questions_asked=self.trace.counters.human_questions,
                human_question_budget=self._rank_config.human_question_budget,
                accept_gaps=self._accept_gaps,
                ri_unavailable=self._ri_unavailable,
                extract_failed=self.claims.extract_failed,
            ).model_copy(
                update={
                    "decision": "needs_hitl",
                    "reason": "step bound reached without a terminal sufficiency decision",
                }
            ),
            [],
        )

    async def _bootstrap(self) -> None:
        self.trace.append(SessionEventKind.START, request=self.request[:240])
        self.claims = extract_claims(self.request, self._adapter, extra_intake=self._extra_intake)
        self.trace.counters.llm_calls += 1
        self.trace.append(
            SessionEventKind.EXTRACT,
            claim_count=len(self.claims.claims),
            extract_failed=self.claims.extract_failed,
        )
        classified = classify_claims(self.claims, self.evidence, None)
        self.claims = classified.claim_set
        self.queue.apply_claims(self.claims)
        seed_slots_from_decisions(self.queue, self.claims)
        try:
            hits_before = self._cache.hits
            self.snapshot = await build_snapshot(self._ri, cache=self._cache)
            if self._cache.hits > hits_before:
                self._snapshot_ri = 1
                self.trace.counters.snapshot_cache_hits += 1
            else:
                self._snapshot_ri = 3
            self._session = RetrievalSession(snapshot=self.snapshot)
            self.trace.append(
                SessionEventKind.SNAPSHOT,
                catalog_hash=self.snapshot.catalog_hash,
                index_state=self.snapshot.index_state,
                cache_hit=self._cache.hits > hits_before,
            )
        except SnapshotError as exc:
            self._ri_unavailable = True
            self._ri_unavailable_reason = str(exc)
            self.trace.append(SessionEventKind.SNAPSHOT, error=str(exc), unavailable=True)
        self._bootstrapped = True
        self._refresh_counters()

    async def _retrieve_and_auto(self) -> list[AutoAnswer]:
        autos: list[AutoAnswer] = []
        if self._session is not None and self.snapshot is not None:
            for _ in range(_MAX_INNER):
                due = [
                    question
                    for question in self.queue.activated()
                    if question.evidence_plan is not None and question.id not in self._retrieved
                ]
                for question in due:
                    await self._retrieve_slot(question)
                classified = classify_claims(self.claims, self.evidence, self.snapshot)
                self.claims = classified.claim_set
                seeded = seed_slots_from_decisions(self.queue, self.claims)
                if seeded:
                    self.trace.append(SessionEventKind.SEED, slot_ids=seeded)
                report = evaluate_slots(
                    self.queue.activated(),
                    self.claims,
                    snapshot=self.snapshot,
                    evidence=self.evidence,
                    config=self._rank_config,
                )
                self.claims = report.classified
                new_auto = False
                for item in report.auto:
                    if item.question_id in self.queue.answers or item.auto_answer is None:
                        continue
                    self.queue.answer(item.question_id, item.auto_answer.answer, source="auto")
                    autos.append(item.auto_answer)
                    self.trace.counters.auto_answers += 1
                    self.trace.append(
                        SessionEventKind.AUTO_ANSWER,
                        question_id=item.question_id,
                        answer=item.auto_answer.answer,
                        evidence_refs=item.evidence_refs,
                        status=item.status,
                    )
                    new_auto = True
                if not due and not new_auto and not seeded:
                    break
        else:
            seed_slots_from_decisions(self.queue, self.claims)
        self.trace.append(SessionEventKind.ACTIVATE, slot_ids=self.queue.activated_ids())
        self._refresh_counters()
        return autos

    async def _retrieve_slot(self, question: Question) -> None:
        assert self._session is not None and self.snapshot is not None
        plan = parse_evidence_plan(question.evidence_plan or {})
        try:
            records = await execute_plan(
                plan, self.snapshot, self._ri, self._session, self.claims
            )
        except StaleIndexError as exc:
            self._ri_unavailable = True
            self._ri_unavailable_reason = str(exc)
            self._retrieved.add(question.id)
            self.trace.append(
                SessionEventKind.RETRIEVE,
                question_id=question.id,
                error=str(exc),
                unavailable=True,
            )
            return
        self.evidence.extend(records)
        self._retrieved.add(question.id)
        self.trace.append(
            SessionEventKind.RETRIEVE,
            question_id=question.id,
            need=plan.need,
            records=len(records),
            ri_calls=self._session.ri_calls,
        )

    def _sufficiency(self) -> SufficiencyReport:
        report = evaluate_slots(
            self.queue.activated(),
            self.claims,
            snapshot=self.snapshot,
            evidence=self.evidence,
            config=self._rank_config,
        )
        self.claims = report.classified
        selected = [
            row.question_id
            for row in (report.ranking.ranked if report.ranking is not None else [])
            if row.selected and row.question_id not in self.queue.answers
        ]
        remaining_budget = self._rank_config.human_question_budget
        asked = self.trace.counters.human_questions
        if asked >= remaining_budget:
            selected = [
                qid
                for qid in selected
                if self.queue.get(qid).mandatory
            ]
        return evaluate_sufficiency(
            claim_set=self.claims,
            mandatory_unanswered=self._mandatory_unanswered(),
            askable_remaining=selected,
            evidence_coverage=self._evidence_coverage(),
            human_questions_asked=asked,
            human_question_budget=remaining_budget,
            accept_gaps=self._accept_gaps,
            ri_unavailable=self._ri_unavailable,
            extract_failed=self.claims.extract_failed,
        )

    def _ask_one(self, autos: list[AutoAnswer]) -> EngineStepResult | None:
        report = evaluate_slots(
            self.queue.activated(),
            self.claims,
            snapshot=self.snapshot,
            evidence=self.evidence,
            config=self._rank_config,
        )
        ranked = report.ranking.ranked if report.ranking is not None else []
        order = list(report.ranking.selected_ids) if report.ranking is not None else []
        by_id = {row.question_id: row for row in ranked}
        self.trace.append(
            SessionEventKind.RANK,
            selected_ids=order,
            scores={row.question_id: row.score for row in ranked},
        )
        asked = self.trace.counters.human_questions
        budget = self._rank_config.human_question_budget
        for qid in order:
            row = by_id.get(qid)
            if row is None or not row.selected or qid in self.queue.answers:
                continue
            question = self.queue.get(qid)
            if asked >= budget and not question.mandatory:
                continue
            decision = next(item for item in report.ask if item.question_id == qid)
            self._pending = decision
            self.trace.append(
                SessionEventKind.ASK,
                question_id=decision.question_id,
                mandatory=decision.mandatory,
                score=decision.ranking_score,
                reason=decision.reason,
            )
            result = _ask_result(decision, self.trace.counters)
            result.auto_answers = autos
            result.sufficiency = evaluate_sufficiency(
                claim_set=self.claims,
                mandatory_unanswered=self._mandatory_unanswered(),
                askable_remaining=[decision.question_id],
                evidence_coverage=self._evidence_coverage(),
                human_questions_asked=asked,
                human_question_budget=budget,
                accept_gaps=self._accept_gaps,
                ri_unavailable=self._ri_unavailable,
                extract_failed=self.claims.extract_failed,
            )
            return result
        return None

    def _exit(self, gate: SufficiencyReport, autos: list[AutoAnswer]) -> EngineStepResult:
        spec = _spec_with_gaps(project_spec(self.claims), self.queue, gate.decision)
        self.trace.counters.final_outcome = gate.decision  # type: ignore[assignment]
        self.trace.append(
            SessionEventKind.EXIT,
            outcome=gate.decision,
            reason=gate.reason,
        )
        self._refresh_counters()
        result = EngineStepResult(
            action=gate.decision,
            reason=gate.reason,
            spec=spec,
            sufficiency=gate,
            auto_answers=autos,
            counters=self.trace.counters.model_copy(),
        )
        self._terminal = result
        return result

    def _mandatory_unanswered(self) -> list[str]:
        return [
            question.id
            for question in self.queue.applicable()
            if question.mandatory and question.id not in self.queue.answers
        ]

    def _evidence_coverage(self) -> float:
        planned = [
            question
            for question in self.queue.applicable()
            if question.evidence_plan is not None
        ]
        if not planned:
            return 1.0
        covered = sum(1 for question in planned if question.id in self._retrieved)
        return round(covered / len(planned), 6)

    def _refresh_counters(self) -> None:
        session = self._session
        traces = session.traces if session is not None else []
        ri_used = session.ri_calls if session is not None else 0
        self.trace.counters.ri_calls = self._snapshot_ri + ri_used
        self.trace.counters.ri_cache_hits = sum(1 for item in traces if item.cache_hit)
        self.trace.counters.semantic_calls = sum(
            1 for item in traces if item.signal == "semantic" and item.ri_method
        )
        self.trace.counters.session_budget_consumed = ri_used


def _ask_result(decision: SlotDecision, counters: SessionCounters) -> EngineStepResult:
    return EngineStepResult(
        action="ask",
        reason=decision.reason,
        question_id=decision.question_id,
        question_text=decision.question_text,
        mandatory=decision.mandatory,
        counters=counters.model_copy(),
    )


def _append_claim(claim_set: ClaimSet, question: Question, text: str) -> ClaimSet:
    kind = _CATEGORY_KIND.get(question.category, ClaimKind.FUNCTIONAL)
    if "acceptance" in question.text.lower():
        kind = ClaimKind.ACCEPTANCE
    nfr_type = question.category if kind is ClaimKind.NFR else None
    claim = Claim(
        id=f"ans-{question.id}",
        kind=kind,
        text=text,
        status=EpistemicStatus.DECISION,
        provenance=Provenance(source="engineer", ref=question.id),
        nfr_type=nfr_type,
    )
    return claim_set.model_copy(update={"claims": [*claim_set.claims, claim]})


def _spec_with_gaps(
    spec: RequirementsSpec, queue: QuestionQueue, outcome: str
) -> RequirementsSpec:
    filled: RequirementsSpec = {**spec, "open_ambiguities": list(spec["open_ambiguities"])}
    filled["assumptions"] = list(spec["assumptions"])
    for question in queue.applicable():
        if question.id in queue.answers:
            continue
        note = f"unanswered {question.id}: {question.text}"
        if question.mandatory:
            filled["open_ambiguities"].append(note)
        elif outcome == "accept_gaps":
            filled["assumptions"].append(f"accepted gap {question.id}: {question.text}")
    return filled
