# Development Strategy

This document defines *how* work happens inside every phase and section of `roadmap.md` and `phases/`. It is the operating manual for a single engineer executing this plan. Read this once before starting Phase 0, and re-read the relevant part whenever a phase feels like it's sprawling.

---

## 1. Core Philosophy

This is a research-heavy, experimental platform (per the brief). Two forces are in tension:

- **Research needs room to be wrong.** Agent behavior, prompt strategies, and even architectural choices (graph DB, vector store) are expected to change as evidence comes in.
- **A platform this safety-sensitive (fail-closed principles, human approval gates, production deploy governance) cannot be built by accumulating untested code for 16 phases and testing at the end.**

The resolution: **modularity absorbs the research uncertainty; the per-task lifecycle absorbs the safety requirement.** Every module sits behind a narrow interface (`ModelAdapter`, `RepositoryIntelligence`, `Validator`/`ApprovalGate` templates) specifically so that when research says "the graph DB choice was wrong" or "this prompting strategy doesn't work," the blast radius of the fix is one module, not a rewrite. Every unit of engineering work — regardless of which module it's in — follows the same eight-step lifecycle so nothing ships untested even under research pressure to move fast.

---

## 2. The Per-Task Lifecycle (Non-Negotiable)

Every atomic task in every section of every phase follows this loop. This is not a suggestion — a task is not "done" until it has gone through all eight steps.

```
   Plan
    │  What exactly am I building, and what does "correct" look like?
    ▼
 Implement
    │  Write the minimum code that satisfies the plan.
    ▼
   Run
    │  Actually execute it. Not "it should work" — run it.
    ▼
   Test
    │  Automated test (unit/integration) covering the behavior.
    ▼
  Verify
    │  Confirm against the section's acceptance criteria, not just "tests pass."
    ▼
 Demonstrate
    │  Produce observable evidence: a log line, a screenshot, a trace, a
    │  CLI output — something a reviewer (even future-you) can look at
    │  without re-running the code.
    ▼
  Commit
    │  Small, scoped commit. Message states what capability now exists.
    ▼
 Continue
    │  Move to the next atomic task.
```

**Why "Demonstrate" is its own step, separate from "Test":** a passing pytest suite proves the code does what the test asserts. It does not prove the *feature is real* in a way a human (or future you, six weeks later) can trust without re-reading the test. Every section in every phase therefore has an explicit "Expected Demo" — a manual, human-observable action (a CLI command, a UI interaction, a curl request) that produces visible evidence the capability works end-to-end.

**Never defer testing to the end of a phase.** If a section's acceptance criteria can't be verified yet because a later section in the same phase isn't built, that's a signal the sections are sequenced wrong or too coarse — split them.

---

## 3. Definition of "Phase" vs. "Section" vs. "Atomic Task"

| Level | Granularity | Rule |
|---|---|---|
| **Phase** | Days to ~2 weeks of solo work | Must leave the system in a strictly more capable, still fully-runnable state than before. Must have one live, end-to-end demo distinct from any single section's demo. |
| **Section** | Half a day to ~2 days | Focused on exactly one architectural objective (e.g., "Tree-sitter Symbol Index," not "Repository Intelligence"). Has its own manual test procedure and demo, independent of other sections in the phase. |
| **Atomic task** | 1–4 hours | A meaningful implementation unit — "implement the `get_callers` traversal with depth limit and unit tests," not "create the `repo_intel/` folder." If a task feels like it would take 15 minutes, it's not atomic at the right grain — fold it into a neighboring task. If it feels like it would take a full day, split it. |

---

## 4. Continuous Testing Strategy

Three test layers exist from Phase 0 onward and grow with the system — never introduced "later":

1. **Unit tests** — pure functions and isolated classes (the Confidence Model formula, `resolve_workflow_profile()` rules, MASC schema checks). Fast, run on every commit.
2. **Integration tests** — a real Postgres (via `docker-compose` / testcontainers) and a real (small, fixture) **working tree** for Repository Intelligence tests (files on disk, including uncommitted edits — not a git HEAD snapshot). Slower; run before marking a section complete.
3. **Contract tests** (from Phase 2 onward) — every `ModelAdapter` implementation, and later every `Validator`/`ApprovalGate` config, must pass the same shared contract suite. This is what makes "add a second model provider with zero orchestration changes" (Phase 16's acceptance test) actually verifiable rather than aspirational.

From Phase 15 onward, a fourth layer exists: **benchmark/regression tests against the golden dataset** via `EvaluationEngine` (`packages/evaluation/` must not import LangGraph). These are allowed to be slow and are not run on every commit (subset on PR, fuller set on main/nightly), but must run before any prompt, model, or agent-logic change is considered complete.

**Rule for flaky or LLM-output-dependent tests:** assert on structure (schema conformance, required fields present, confidence bounds) and on deterministic sub-behaviors (tool calls made, retrieval invoked) rather than on exact LLM text output. Where exact-output determinism matters (routing rules, MASC schema checks, confidence formula), those are pure functions with no model call — write them that way specifically so they're fully deterministic to test.

---

## 5. Continuous Demonstration Strategy

Every phase's README specifies one **live demo** — an end-to-end script or UI walkthrough that a person unfamiliar with the code could watch and understand what the phase added. Concretely:

- Phases 0–2 (foundations): CLI-driven demos (a script that creates a Task, runs it through the sandbox, prints the trace).
- Phases 3–8 (core agents): a combination of CLI + inspectable Postgres state (query the `tasks`/`hitl_log`/`cost_tracking` tables to show real rows) + optional Langfuse UI via OTLP (not required for the demo to count).
- Phase 9 onward: the UI itself becomes the primary demo surface — screenshots or short recordings of the relevant screen(s) showing the new capability live.
- Phase 15 onward: dashboards (Grafana/KPI screens) become part of the demo — a phase isn't "demoed" by code working once, it's demoed by the metric that phase was supposed to move actually moving.

Keep a running `docs/demos/` log (screenshots, short clips, or terminal recordings) is optional but strongly recommended — six months in, this is the fastest way to answer "when did X actually start working."

---

## 6. Modular Architecture & Refutability

Every module boundary in this system exists to make a specific future change cheap. When adding code, ask "which module does this belong to, and would this change ever need to happen without touching anything else?" If the answer is "these two things always change together," they belong in the same module; if "these might independently change," they must not share internals.

Concrete seams to protect (do not let agent code, orchestration code, or API code reach past these interfaces):

- `ModelAdapter` (§I.1) — no provider SDK import outside `model_adapters/`. This is a **grep-verifiable** acceptance criterion in Phase 2 for a reason: run `grep -r "import openai\|import zhipuai" --include="*.py" | grep -v model_adapters/` (or equivalent) as an actual CI check, not just a code-review habit.
- `RepositoryIntelligence` (§G.6) — no agent imports the graph client, vector client, or Zoekt client directly. Everything goes through the interface. Phase 03 indexes the **local working tree** via explicit `index`/`reindex` (content hashes); git is not the retrieval source of truth (`docs/phases/phase-03/section-05.md`).
- `ApprovalGate` / `Validator` templates (§E.1) — resist creating a bespoke agent class for a new checkpoint or validation rule; add a new *config instance* of the existing template instead. If a genuinely new template shape is needed, that's a real architectural decision — write it down (see §8 below) before building it.
- Workflow routing logic lives only in `workflow_engine/policy.py` (§F.3) — never let an agent or API handler contain an inline "if risk_tier == critical" branch. If routing logic starts leaking outside this module, that's a sign a rule is missing from the ordered rule table.

---

## 7. Research & Experimentation Discipline

Because this is explicitly an experimental platform, some sections are marked "Research Opportunities" — these are invitations to deviate, not requirements. Treat them as a separate, clearly-labeled track:

- Never let a research spike block a phase's core acceptance criteria. If confidence-formula recalibration (§B.4) or a new agent specialization technique (§E.3) is worth exploring, do it in a branch/notebook against the golden dataset (once Phase 15 exists) or a small labeled set, and only promote it into the main path once it beats the existing baseline on a stated metric.
- Every research change that gets promoted must go through the same PR review as any other code change (per §N's "Policy changes deployed without review" mitigation) — including changes to `configs/workflow_policies/`, prompt templates, and confidence weights.
- Keep a lightweight `docs/decisions/` log (ADR-style, one file per non-obvious decision — e.g., "why NetworkX before Neo4j," "why we recalibrated confidence weights on date X") for anything that isn't self-evident from the code. This is cheap insurance against re-litigating settled questions.

---

## 8. Handling Scope Creep Mid-Phase

If, while implementing a section, you discover the blueprint under-specifies something (this will happen — the blueprint itself flags several such gaps, e.g., Feedback Agent behavior, prompt engineering strategy):

1. Make the smallest reasonable decision that unblocks the current atomic task.
2. Write it down in that section's file under a `> **Implementation Note:**` callout, or in `docs/decisions/` if it's significant enough to affect other phases.
3. Do not silently expand the section's scope to "fully solve" the gap — finish the atomic task, note the gap, move on. Revisit in the phase's "Future Improvements" list if it needs more than a note.

---

## 9. Definition of "Done" for a Phase

A phase is done when, and only when:

1. Every section's acceptance criteria pass.
2. The phase's live demo can be run/shown from a clean environment (`docker-compose up` + documented setup steps) — not "works on my currently-running instance."
3. The system is in a state where the *next* phase's first atomic task can start without unplanned rework.
4. All new/changed code has unit and (where applicable) integration test coverage — no "I'll test it later" carried across a phase boundary.
5. The phase's risks and future-improvements have been reviewed once — not necessarily acted on, but consciously accepted or deferred.

This definition is intentionally stricter than "the code compiles" — see `roadmap.md` for how each phase's specific completion criteria (inherited from the blueprint's own Part C table) map onto this general definition.
