# Platform Rebuild Guide

A self-contained specification for rebuilding the semi-autonomous software-engineering platform from scratch.

It is written for an engineer or AI agent with **no prior context**. After reading it you should know:

- what the platform does
- what every feature is for
- what each feature's data looks like and how it behaves
- what is in scope now and what comes later
- what went wrong last time

> **The tech stack is deliberately not decided here.**
> The old blueprint (`final_plan.md`) and the old code assume specific frameworks, databases, and services. Treat those as history, not as recommendations.
>
> This guide describes behavior, data shapes, and rules only. Product names appear in section 7 (Tools) as options to evaluate, never as decisions. Section 13 lists the open stack decisions and the requirements each choice must meet.

---

## 0. How to use this guide

**Reading order**

- **New to the project.** Read sections 1 → 2 → 3 → 4. That is about 20 minutes and gives the full picture.
- **Building one feature.** Read its spec in section 5, the tools it needs in section 7, and the warnings in sections 9–10.
- **Checking a decision.** Section 11 lists every resolved conflict (D1–D20), and section 12 lists every chosen number. If anything else disagrees with them, sections 11 and 12 win.
- **Working on code search or context.** Read section 6 (Repository Intelligence).
- **Choosing the stack.** Read section 13.

**Every feature spec in section 5 uses the same template:**

| Field | Answers |
|---|---|
| What and why | What the feature is and what problem it solves |
| How it works | Step-by-step behavior |
| What it looks like | Data shapes and concrete examples |
| Rules | Invariants that must always hold |
| When things fail | Failure behavior (always fail closed) |
| Scope | MVP now vs. later |
| Done when | A measurable acceptance test |
| Old build | What existed before, if anything |

**Notation**

- `§X.Y` means a section of `final_plan.md`.
- Data shapes use a neutral notation:
  - `field: type`
  - `?` means optional or nullable
  - `[T]` means a list of T
  - `a | b` means one of
  - `{k: v}` means a map
- A field marked **append-only** can only grow. Writers add new items and never rewrite old ones.
- A field marked **replace** is overwritten as a whole.

**Contents**

1. What we are building
2. Glossary
3. Principles
4. System map: components and agent roster
5. Feature specs (5.1–5.20, plus 5.5a)
6. Repository Intelligence in depth
7. Tools: build it yourself or use a third-party option
8. Scope cuts: cut, simplify, keep
9. Lessons learned
10. Pitfalls from the old build
11. Resolved decisions (former contradictions)
12. Decided numbers (former gaps)
13. Open tech-stack decisions
14. Done criteria and build order
15. Appendix: old repo map (reference only)

---

## 1. What we are building

### 1.1 One-paragraph summary

A person submits a unit of work against an existing code repository. That might be a feature request, bug, hotfix, refactor, or migration.

The platform runs the work through the full software lifecycle:

- intake
- requirements
- design
- implementation
- QA
- review
- release
- monitoring

Work is split three ways:

- **Narrow AI agents** do the reasoning steps.
- **Deterministic code** does scheduling, merging, and checks.
- **Humans** handle anything ambiguous or irreversible.

The output is a reviewed pull request with an evidence bundle. With approval, that change is then deployed through the team's existing CI/CD.

The priorities are correctness, safety, and explainability over raw speed. Repositories with 100k+ files are a design constraint from day one, even though the first version targets small repos.

### 1.2 Why a rebuild

The old repo built several solid pieces:

- the foundations
- the model layer
- Repository Intelligence
- the requirements engine (as a library)
- part of intake

But the workflow itself was eight placeholder steps in a straight line. Every dynamic part existed only on paper: topology selection, waves, merge coordination, feedback loops, and policy routing.

The rebuild keeps the designs, contracts, algorithms, and lessons. It does **not** inherit the old stack.

| Area | Old state | Carry over as |
|---|---|---|
| Foundations: task record, budget kill switch, sandbox, telemetry | Built and tested, with bugs | The contracts plus the fixes in section 10 |
| Durable workflow: checkpoints, pause/resume, crash recovery | Built; phase steps were stubs | Patterns and the crash test; rewrite the workflow |
| Model layer: adapter, router, pricing, circuit breaker | Built and contract-tested | The design and the contract test suite |
| Repository Intelligence | Built; 96.2% success@5 on the benchmark | The design, the algorithms, and the benchmark |
| Requirements engine | Built as a library; never wired into the workflow | The design, the question bank, and the gate logic |
| Intake and planning | Partial | Templates and finished wiring |
| Design, implementation, QA, release, UI, policy, evaluation | Docs only | The specs in section 5 |

### 1.3 Goals and constraints

- **Model-independent.** Swapping the provider or model must need zero workflow changes.
  - The current provider is GLM, through an OpenAI-compatible chat API with function calling.
  - The model only *requests* tool calls. The platform executes them.
- **Explicit memory.** The platform decides exactly what context each agent sees. No hidden framework memory, no hidden files written by a framework.
- **Dynamic but deterministic.**
  - Deterministic rules choose the active agents, the approvals, and the execution shape at runtime, from task properties and repository facts.
  - An LLM never decides to spawn agents.
- **Humans own irreversible actions.** Production deploys, merges to protected branches, and data migrations always need a human.
- **Fail closed.** Uncertainty or errors produce more human oversight, never more autonomy.
- **Buildable by one engineer.** Prefer simple, testable, deterministic parts, and grow them over time.

**Non-goals (§A.3)**

- A general autonomous agent for unscoped requests.
- A replacement for architects on high-blast-radius decisions.
- Real-time pair programming. The platform is asynchronous and review-gated.
- Multi-tenancy at MVP.

### 1.4 The lifecycle at a glance

```text
                    ┌──── clarifying questions to a human ────┐
request ─► INTAKE ─► REQUIREMENTS ─►[scope gate]─► (bug/hotfix: BUG REPRODUCTION)
        ─► DESIGN ─►[design gate]
        ─► IMPLEMENTATION (waves of isolated workers) ─► QA ─►[release gate]
        ─► REVIEW ─►[PR gate]─► RELEASE ─►[deployment gate]─► MONITORING ─► DONE

Bug reproduction is the last step of the requirements phase. It runs after the scope gate and before any design or fix, and it is not a separate phase (decision D7).
Hotfixes skip the full design phase (5.10 agent selection).

Backward edges (each one is a named feedback loop, section 5.11):
  QA test/spec failure         ─► IMPLEMENTATION
  QA finds a design defect     ─► DESIGN        (human approves the loop)
  review requests changes      ─► IMPLEMENTATION
  design finds a requirement gap ─► REQUIREMENTS (human approves the loop)
  production incident          ─► a NEW task, linked by lineage (never back into the old one)

Any state can go to BLOCKED: budget exceeded, loop cap reached, or a human is needed.
BLOCKED is a holding state; a human can resume the task to the phase it came from.
Any non-terminal state can go to CANCELLED. DONE and CANCELLED are terminal.
```

### 1.5 Worked example, end to end

**Request.** "Add soft-delete for users so admins can restore accounts within 30 days."

This example shows the **full design**: all five gates and the full topology rules. The MVP uses the simplified versions in section 8.2. For example, the release gate is folded into the PR gate (decision D6).

**1. Intake.** The Planning Manager makes one fast LLM call to classify the request:

```json
{"type": "feature", "methodology": "agile", "risk_tier": "medium",
 "repo_refs": [{"repo_id": "core-api", "architecture": "modular_monolith"}]}
```

- The task record is created with the default budget: 2,000,000 tokens, $20, and 3 retries per step.
- The workflow profile is the most conservative one: every agent on, all approvals, parallelism capped at 2.

**2. Requirements.** These steps follow section 5.6.

- **Extraction.** One LLM call turns the request into claims:
  - "soft-delete users" is an OBJECTIVE, status DECISION, source request.
  - "restore within 30 days" is FUNCTIONAL, status DECISION, source request.
  - Whether the change touches personal data is UNKNOWN.
- **Unknown data flags activate security questions (fail closed).**
- **Repository Intelligence auto-answers what the code already says:**
  - "The project uses a relational DB" is a FACT, from the manifest.
  - "`User` model exists at `db/models/user.py::User`" is a FACT, from a symbol lookup.
- **The human is asked two questions, one at a time:**
  - "What compliance requirements apply (auth, payments, PII)?" The answer is "GDPR: hard-delete after 30 days."
  - "Must the migration be zero-downtime?" The answer is "yes."
- **Sufficiency gate.** Mandatory slots are answered and there is no contradiction, so the result is `spec_ready`.
- **Outputs.**
  - A `RequirementsSpec`.
  - A handoff packet of at most 2,000 tokens.
  - A computed confidence score of 0.84, above the requirements floor of 0.80.
- **Policy re-resolution.** Now that confidence exists, the workflow profile is resolved again (5.10). Medium risk matches Rule 5, so all five gates stay.
- **Scope gate.** A human approves.

**3. Design.**

- The Design Manager and the Repo Architecture Analyst produce an `ArchitectureDoc` covering five pieces:
  - a migration adding `deleted_at`
  - a model filter
  - repository methods
  - restore and purge API endpoints
  - an admin UI toggle
- The design Validator checks boundaries, contracts, and failure handling.
- Confidence at design exit is 0.88, above the design floor of 0.85. This is the value the wave planner reads for TP-02.
- **Design gate.** A human approves.

**4. Implementation.** These steps follow section 5.8.

- **Decomposition.** The Implementation Manager makes **one** LLM call and returns five subtasks with declared dependencies:
  - A: migration
  - B: model, depends on A
  - C: repository, depends on B
  - D: API, depends on C
  - E: admin UI, independent
- **Wave planning (deterministic).** `plan_execution_waves()`:
  - verifies the dependency edges through Repository Intelligence
  - finds no hard gate
  - gets width 4 from TP-08, then the profile cap of 2 → width 2
  - levelizes into waves `[A, E] → [B] → [C] → [D]`
  - labels the plan `hybrid`
- **Wave 0.** Two isolated workers, each in its own git worktree.
  - Each produces a diff and a Worker Coordination Packet.
  - Each branch passes its own Validator.
  - Fan-in merges both and writes a Wave Handoff Note for wave 1, for example: "interface changed: `users.deleted_at` column added by A."
- **Waves 1–3** run the same way, each based on the merged result so far.
- **Integration Validator** runs once on the merged result, and it passes.
- **LLM calls for the whole phase on the happy path:** 1 Manager + 5 workers + 1 Integration Validator = **7**.

**5. QA.** These steps follow section 5.12.

- The impact set of the changed files selects which tests to run.
- These checks always run:
  - lint/type
  - secrets scan
  - dependency audit
  - impacted tests
  - Spec QA against the acceptance criteria
- SAST runs too, because risk is at least medium.
- The evidence bundle is stored.
- **Release gate.** A human approves.

**6. Review.** The Review Manager checks the diff against the design and standards, and a PR is opened. **PR gate:** a human approves the merge.

**7. Release.** The Release Manager triggers the team's existing CI/CD with a canary strategy. **Deployment gate** (always human for production): approved.

**8. Monitoring.** A bake-in period compares canary health against the baseline.

- If clean, the task is DONE and the final report shows the cost, human-question count, files changed, and KPIs.
- If an incident occurs, a *new* task is created, with `lineage.root_incident_id` set.

---

## 2. Glossary

| Term | Meaning |
|---|---|
| **Task** | One unit of work: one request, one durable record. Its id also serves as the workflow run id. |
| **Phase** | One lifecycle stage: intake, requirements, design, implementation, qa, review, release, monitoring. Terminal states are done and cancelled. Blocked is a holding state a human can resume from. |
| **Working state** | The in-flight state of one task run, checkpointed after every step. It is different from the durable Task record. |
| **State checkpoint** | A durable snapshot of working state, used to resume after a crash or a human wait. It is not the same as an approval gate. |
| **Agent** | One narrow LLM-backed role with a fixed input schema, output schema, and tool set. |
| **Manager** | A phase-level agent that coordinates a phase: it decomposes and replans. Only managers may replan. |
| **Worker / CodeGen sub-agent** | An implementation agent that does exactly one subtask in an isolated git worktree. It never talks to other workers. |
| **Validator** | An independent checker of another agent's output. It is a config-driven template; many validators use tools only. |
| **ApprovalGate** | A config-driven template that pauses the workflow for a human decision at a named point. |
| **HITL** | Human in the loop. Any pause that waits for a person. |
| **Fan-in Coordinator** | Deterministic code, with no LLM, that merges a wave's branches, detects conflicts, and prepares the next wave. |
| **Wave Scheduler** | Deterministic code that dispatches the current wave's subtasks to workers. It is the only component allowed to dispatch. |
| **TaskDecomposition** | The Manager's output: *what* to build, as subtasks with declared dependencies. |
| **SDG** | Subtask Dependency Graph. Subtasks are nodes; typed, evidence-backed dependency edges connect them. |
| **ExecutionPlan** | *When* each subtask runs: an ordered list of waves. It is produced deterministically from the SDG. |
| **Wave** | A group of subtasks with no blocking dependencies between them, dispatched together. |
| **Topology class** | A derived label for a plan: `sequential`, `parallel`, or `hybrid`. It is never an input. |
| **TP rules** | Topology policy rules TP-01..TP-08: deterministic rules that cap wave width. |
| **Demotion** | Rerunning conflicting subtasks of a wave one after another, instead of in parallel. |
| **Amendment** | Adding a newly discovered blocking edge to the remaining plan. It can only narrow the plan, never widen it. |
| **plan_version / attempt_number** | Counters that make every dispatch uniquely identifiable and idempotent. |
| **WCP** | Worker Coordination Packet. The structured self-report every worker emits when it exits. |
| **ClarificationEscalation** | A blocked worker's structured "I cannot continue safely" report. |
| **FeedbackReport** | A validator's structured rejection of a finished output, saying exactly what to fix. |
| **ReplanContext** | Structured history given to a Manager when replanning, so no attempt starts from zero. |
| **PhaseHandoffPacket** | A capped-size summary passed from one phase to the next. Details travel by pointer. |
| **WaveHandoffNote** | A capped-size summary passed from finished waves to the next wave. It is built without an LLM. |
| **Blackboard** | A pointer-addressed artifact store for diffs, logs, and evidence. It keeps large content out of prompts and state. |
| **Pointer** | A Blackboard reference in the form `{task_id}/{kind}/{uuid}`. |
| **RI** | Repository Intelligence: the long-lived code-understanding service (section 6). |
| **symbol_id** | A stable symbol identity in the form `{file_path}::{qualified_name}`, for example `auth/service.py::AuthService.login`. |
| **Architecture summary** | A JSON overview of the repo, generated from the parsed syntax tree, never by an LLM. It goes into every agent's prompt. |
| **Repo map** | A ranked, token-budgeted list of the files and signatures most relevant to the current task. It uses personalized PageRank. |
| **PPR** | Personalized PageRank. PageRank whose random restarts jump back to task-specific seed files. |
| **RRF** | Reciprocal Rank Fusion. It merges ranked lists from different retrieval signals. |
| **WorkflowContext** | Facts about the task and repo: risk, work type, repo scale, DB/API/UI changes, and so on. Policy rules use it as their input. |
| **WorkflowProfile** | The policy output: active agents, approvals, QA depth, model tier, max parallelism, budget. |
| **Risk tier** | low, medium, high, or critical. It drives approvals, QA depth, and parallelism. |
| **Work type** | new_project, feature, bug, hotfix, refactor, migration, tech_debt, or maintenance. |
| **Confidence score** | A 0–1 composite of four measured signals. A missing signal is never guessed. |
| **MASC** | The post-step output checker, run on every agent output: schema, then confidence, then semantic drift. |
| **Context Ledger** | Pinned, never-compressed facts about the task: decisions, constraints, interface contracts, and failures. |
| **Context tiers T0–T4** | The prompt layout, from a stable prefix through pinned facts, working window, compacted history, and pointers. |
| **Evidence bundle** | QA results attached to the PR and shown at approval gates. |
| **Kill switch** | Forces a task to BLOCKED when it exceeds its budget or step-visit ceiling. |
| **Circuit breaker** | Pauses a task (it does not fail it) when the model provider is down. |
| **ModelAdapter** | The only interface through which the platform talks to any model provider. |
| **Model tier** | fast_cheap, balanced, or frontier. The router maps tiers to concrete models. |
| **Fail closed** | On error or uncertainty, choose the safer path: more checks, a human, or sequential execution. |
| **Claim / epistemic status** | One requirement statement, with how we know it: FACT, INFERENCE, DECISION, UNKNOWN, or CONTRADICTION. |
| **Slot / question bank** | Config-defined requirement questions, activated by predicates. |
| **Evidence plan** | A per-slot recipe for which RI calls can answer the slot automatically. |
| **Sufficiency gate** | The deterministic exit check of the requirements loop. |
| **success@5** | A retrieval metric: did any of the top 5 results contain the right answer? |
| **Worktree** | A separate git working directory and branch for one worker attempt. |
| **task_base_sha / integration HEAD** | The commit the task started from, and the latest merged result of finished waves. |
| **Lineage** | Links between tasks: the parent task, and the root incident for incident-driven tasks. |
| **Golden dataset** | Versioned, labeled tasks used to measure the platform and catch regressions. |
| **Shadow mode** | The platform proposes; a human decides. The two are compared before any autonomy is granted. |

---

## 3. Principles

From §A.2. These settle most design questions, so check a new idea against them first.

1. **Plan more than you implement.** Spend reasoning budget on requirements and design. Use cheaper models for code once the design is approved.
2. **Narrow agents, checked at every handoff.** Nothing moves to the next phase until a validator that is independent of the producer passes it.
3. **Ask, don't guess.** Ambiguity triggers a structured question to a human, never a silent assumption.
4. **Irreversible actions need a human.** Confidence can speed up routing. It never unlocks production deploys, force-pushes, or data migrations.
5. **Deterministic over clever.** Prefer rule tables and named tools over learned or black-box logic.
6. **Model and tool independence is structural.** Enforce it with adapters and import-boundary tests, not with convention.
7. **Incremental over big-bang.** The platform must be useful on a 500-file repo on day one, and scale by strengthening the same design.
8. **Fail closed.** If a scorer, policy, or validator errors, times out, or returns malformed output, the task gets more human oversight.
9. **Workers are isolated on purpose.** Parallel workers never communicate. Cross-worker knowledge is assembled only at Fan-in.
10. **Parallelism follows dependencies, not difficulty.** Measured file, symbol, interface, and shared-resource dependencies decide what runs in parallel. A deterministic, testable function makes that decision.

**Three more rules apply everywhere**

- **Observation never drives control.** Events and traces are write-only from the workflow's point of view. No routing decision may read them.
- **No phase quietly disables an earlier safety check.** Loosening an approval must be an explicit, tested policy rule.
- **Every milestone leaves the main branch runnable** from a clean checkout with one documented command sequence.

---

## 4. System map

### 4.1 Components

| Component | Kind | Purpose | Spec |
|---|---|---|---|
| Durable workflow runner | Infrastructure | Runs phases, checkpoints state, pauses and resumes for humans | 5.2 |
| Task store | Infrastructure | Durable Task records, approvals, the HITL log, costs, events | 5.1 |
| Blackboard | Service | Pointer-addressed artifact store | 5.3 |
| Repository Intelligence | Long-lived service | Code search, symbols, graph, semantic search, repo map | 6 |
| Model layer | Library | ModelAdapter, router, pricing, circuit breaker | 5.15 |
| Sandbox runner | Service | Runs code, tests, and analyzers in isolated containers | 5.18 |
| Policy engine | Pure functions | WorkflowContext → WorkflowProfile; topology rules; feedback-loop registry | 5.10 |
| Requirements engine | Library plus agents | Claims, evidence, questions, sufficiency | 5.6 |
| Wave planner, Wave Scheduler, Fan-in | Deterministic code | Parallel-safe implementation | 5.8 |
| Validators, MASC | Templates plus tools | Independent output checks | 5.9 |
| Approval gates and HITL inbox | Templates plus store | Human decisions | 5.4 |
| Context builder | Library | Assembles each agent's prompt within budget | 5.16 |
| Telemetry sink | Library | Traces, events, metrics; failure-isolated | 5.17 |
| Evaluation engine | Offline service | Scores finished runs | 5.19 |
| API and UI | Application | Submit, watch, approve, answer | 5.20 |
| Integrations | Adapters | Git host, tickets, chat, CI/CD | 5.14 |

### 4.2 Agent roster

These are the agents and validators by phase. "No LLM" rows are listed because they sit in the same slot as an agent. Anything else not listed is deterministic code or a human.

| Phase | Agent | Model tier | Output | Tools |
|---|---|---|---|---|
| Intake | Planning Manager | Fast | Classified Task: type, risk, methodology, repo refs | Architecture summary |
| Requirements | Requirements Analyst (runs the requirements engine) | Strong | `RequirementsSpec` and handoff packet | RI read tools |
| Requirements | Validator (requirements) | Fast | pass/fail plus gaps | Consistency checks |
| Requirements (bug/hotfix only) | Bug Validation Agent | Strong | A reproduction before any fix; QA re-runs it after the fix | Sandbox, read tools |
| Design | Design Manager (with a reflection pass) | Strong | `ArchitectureDoc` | RI read tools |
| Design | Repo Architecture Analyst | Fast | Architecture-fit analysis | RI structural queries, 2 hops from affected modules |
| Design | Security Architect (with a reflection pass) | Strong | Security addendum, threat model | SAST rule lookups |
| Design | Validator (design) | Strong | Checklist pass/fail plus gaps | Checklist |
| Implementation | Implementation Manager | Strong, ×1 per attempt | `TaskDecomposition` | **None** on the decompose call |
| Implementation | CodeGen worker (×N) | Fast, or strong for complex refactors | Diff and WCP, or an escalation | Agent tools (section 7.2) |
| Implementation | Validator (implementation) | **No LLM** | Static check findings | Lint, type, SAST in the sandbox |
| Implementation | Integration Validator | Strong, ×1 per attempt | pass/fail on the merged result | RI callers/callees, sandbox integration tests |
| Implementation | Feedback Agent | Strong | Revised instructions after repeated failure | `ReplanContext`, past outcomes |
| QA | QA Manager | Fast | QA plan from the activation matrix | Policy engine |
| QA | Spec QA Agent | Strong | Requirement compliance report | Structured comparison |
| QA | Regression test writer (a CodeGen worker run) | Fast | New regression tests in its own worktree | Worker tool set (7.2) |
| QA | Exploratory test agent (later) | Fast | Scenarios | UI automation |
| Review | Review Manager | Strong | Review outcome | RI, standards checker |
| Release | Release Manager | Strong | Deployment plan and strategy | CI/CD adapter only |
| Release | Rollback agent | Fast | Rollback execution | CI/CD adapter only |
| Monitoring | Monitoring Manager (owns FL-09) | Fast | Incident or clean bake-in | Health metrics |

**Conditional agents.** These are switched on by agent selection (5.10). All of them come later, not at MVP.

| Agent | Switched on when | Kind | Tools |
|---|---|---|---|
| Migration Validator | DB changes | Validator, no LLM | Migration dry-run and rollback test in the sandbox |
| API Contract Validator | API contract changes | Validator, no LLM | Contract fuzzer against the API spec |
| Consumer Notification | API contract changes with external consumers | Deterministic | Chat or ticket adapter |
| Security QA | Risk ≥ medium | No LLM | SAST; deep dataflow analysis at high risk |
| Performance QA | Risk ≥ high, performance-sensitive path | No LLM | Load-test tool |
| UI QA and Accessibility QA | UI changes | No LLM | UI automation, accessibility scanner |
| Architecture Decision Agent | Greenfield | Strong LLM | RI read tools; writes design records (ADRs) |
| Stage Gate Enforcer | Waterfall methodology | Deterministic | Forces every phase gate on; no phase overlap |
| Shard Coordinator | Enterprise repo | Deterministic | RI index of indices |

**Deterministic components**

- Confidence scorer
- Topology selector (`plan_execution_waves`)
- Wave Scheduler
- Fan-in Coordinator
- Dependency Impact (graph traversal)
- Test runner
- Policy engine

**Human components**

- The six approval gates
- Clarification answers

---

## 5. Feature specs

### 5.1 Task record, working state, and phase state machine

**What and why.** Every unit of work needs two things:

- a durable record of what was asked and what happened, for audit
- a working state that the workflow reads and writes while running

Keeping the two separate means checkpoints stay small, and the audit record survives even if the working state is discarded.

**What it looks like**

```text
Task                                    durable; one per unit of work
  id                  string ≤ 255, unique; also the workflow run id (never truncated)
  title               string
  source              user_request | ticket_import | monitoring_incident | maintenance_scan
  type                new_project | feature | bug | hotfix | refactor | migration | tech_debt | maintenance
  methodology         agile | waterfall | hybrid
  repo_refs           [RepoRef { repo_id, architecture: monolith | modular_monolith | microservices, domain_shard? }]
  risk_tier           low | medium | high | critical
  confidence_score    number 0–1 ?          null = not computed (never default to 0.0 or any guess)
  state               intake | requirements | design | implementation | qa | review | release | monitoring
                      | done | blocked | cancelled
  blocked_from        phase ?               set while blocked, so a human can resume to it
  workflow_profile_id string ?
  budget              { token_ceiling: 2_000_000, cost_ceiling_usd: 20.0, max_retries_per_node: 3 }
  approvals           [ApprovalRecord { checkpoint, approver, decision, evidence_ref, timestamp }]
  lineage             { parent_task_id?, root_incident_id? }
  artifact_refs       [pointer]
  created_at, completed_at?, created_by
```

```text
TaskWorkingState                        checkpointed after every step
  task_id, workflow_profile_id?
  -- phase artifacts
  requirements            RequirementsSpec ?
  architecture            ArchitectureDoc ?
  task_decomposition      TaskDecomposition ?
  implementation_results  [ImplementationResult]        append-only
  qa_evidence             QAEvidence ?
  deployment_record       DeploymentRecord ?
  -- implementation topology (5.8)
  execution_plan          ExecutionPlan ?               replace
  plan_version            int
  current_wave_index      int                           -1 before first dispatch
  topology_decisions      [TopologyDecisionRecord]      append-only
  wave_handoff_notes      [WaveHandoffNote]             append-only
  plan_amendment_count    int
  demotion_ignore_keys    [{subtask_id, plan_version, attempt_number}]   replace
  -- channels (5.3)
  messages                [Message]       append-only; human/system conversation ONLY
  agent_events            [AgentEvent]    append-only; observation only
  feedback_reports        [FeedbackReport]              append-only
  worker_coordination_packets [WCP]                     append-only
  clarification_escalations   [ClarificationEscalation] append-only
  -- safety
  validation_flags        [ValidationFlag]              append-only
  rollback_count          int
  current_rollback_target phase ?
  -- humans (5.4)
  hitl_queue              [HITLRequest]   pending, in-run view
  hitl_history            [HITLRequest]   append-only
  -- intent and context (5.16)
  intent_version, intent_last_updated
  context_ledger          [ContextLedgerEntry]          append-only
  compaction_events       [..]                          append-only
  -- cost
  total_input_tokens, total_output_tokens, total_cost_usd, phase_costs {phase: usd}
```

```text
RequirementsSpec
  functional [string]; non_functional {nfr_type: string}; acceptance_criteria [string]
  open_ambiguities [string]; assumptions [string]; out_of_scope [string]
  version int (bump on every change); approved_at?; approved_by?

ArchitectureDoc
  component_boundaries [obj]; api_contracts [obj]; database_design obj; security_design obj
  deployment_strategy string; adr_ids [string]; version int; approved_at?

ValidationFlag
  source: masc | validator_agent | static_tool;  agent_id; phase
  flag_type: schema_violation | semantic_drift | confidence_below_threshold | tool_error
           | spec_inconsistency | design_gap | security_finding
  severity: info | warning | error | critical;  detail;  rollback_to: phase ?
```

**Memory tiers (§B.3).** Only working memory lives in the workflow state. The other three tiers are reached through tool calls, which keeps checkpoints small and resume fast.

| Tier | Holds | Reached through |
|---|---|---|
| Working | The active task's working state | The state itself |
| Episodic | Past task outcomes, regression history, failure patterns | Query tools |
| Semantic | Code graph, architecture summary, ownership, design decisions | Repository Intelligence |
| Procedural | Human-reviewed playbooks and versioned policy files | Config files under review |

**Allowed transitions**

| From | To |
|---|---|
| intake | requirements |
| requirements | design; implementation (hotfix, which skips full design) |
| design | implementation; requirements (FL-03) |
| implementation | qa |
| qa | review; implementation (FL-06); design (FL-07, FL-08) |
| review | release; implementation (changes requested) |
| release | monitoring |
| monitoring | done; blocked (after an FL-09 automated rollback, a human decides what happens next) |
| any non-terminal state | blocked; cancelled |
| blocked | `blocked_from` (human resume only); cancelled |

- A production incident is never a transition. It creates a new task.
- FL-10 ("roll back to the previous checkpoint") is a workflow replay inside the same phase, not a state transition.

**Rules**

- `Task.state` in the durable store is the source of truth for which phase a task is in.
- Every phase transition updates `Task.state` and emits a phase event.
- Append-only fields: steps return only their *new* items, and the runner appends them.
- A production incident never re-enters an old task. It creates a new Task with `lineage.root_incident_id` set.
- Every Task field must survive a save/load round trip. Test this against the real store.

**When things fail.** A failed save is a hard error, never a silent drop. An invalid transition is rejected and logged.

**Scope**

- **MVP:** all fields, with confidence nullable.
- **Later:** episodic and procedural memory, which need real task history.

**Done when.**

- A round-trip test covers every field.
- Only the transitions in the table above are accepted. Every other pair is rejected by a test.

**Old build.** Built, but the save/load path dropped five fields (pitfall P5).

### 5.2 Durable execution: checkpoints, pause/resume, idempotency, cancellation

**What and why.** Tasks run for hours or days and wait on humans. A crash, deploy, or restart must never lose work or repeat side effects.

**How it works**

1. **Checkpoint after every step.** The working state is checkpointed under run id = `Task.id`.
2. **Pause for a human.**
   - Write the request to the durable HITL log *first*.
   - Then pause the run.
   - Resuming delivers the human's answer to the paused step.
   - Many durable-execution designs **re-run the paused step from its start** on resume. Everything before the pause point must therefore be idempotent, such as "insert HITL row if not already there".
3. **Fixed workflow, dynamic plan as data.**
   - The workflow definition is fixed at startup.
   - The dynamic part, the waves, is *data* in state: the `ExecutionPlan`.
   - A self-re-entering scheduler step executes that data.
   - Changing the workflow definition mid-run would break resume.
4. **Idempotent workers.**
   - The idempotency key is `(task_id, subtask_id, plan_version, attempt_number)`.
   - Before any side effect, a worker checks for an existing result under its key.
   - After a crash, it checks the worktree and the Blackboard first.
   - A retry redoes only the failed step.
   - The same inputs always produce the same outcome.
5. **Bounded loops.** The step-visit ceiling is `max(100, waves × (retries + 1) × 3 + 30)`.
   - The `+ 30` covers the non-implementation phase steps.
   - It is recomputed whenever a new plan is made.
   - Reaching it escalates to a human; it is never a silent stop.
6. **Kill switch.** Before every step, check the budget (tokens, cost) and the step-visit count.
   - If either is exceeded, go to BLOCKED and create a HITL request.
   - Visits are counted as *real step entries*, never derived from other rows.
7. **Cancellation sequence.**
   1. Stop dispatching.
   2. Signal running workers.
   3. Wait a grace period.
   4. Delete worktrees.
   5. Set `Task.state = cancelled`.
   6. Emit `task_cancelled`.
8. **Two kinds of rollback, kept separate.**
   - **Code rollback** is a git operation: discard or revert the branch.
   - **Workflow rollback** is a replay from a prior checkpoint.
   - Never use one for the other.

**Retry policy**

There are two levels, and they are kept separate.

- **Transient errors** (timeouts, malformed responses):
  - The same step is retried in place, up to `max_retries + 1` attempts.
  - Backoff is `min(0.5 × 2^(n−1), 8 s)`.
  - "Provider unavailable" is never retried this way, because the circuit breaker handles it (5.15).
- **Validator rejections** (the output was valid but wrong) follow the escalation ladder in 5.10:
  - At 2 rejections, the step moves up one model tier.
  - At `max_retries_per_node` (3) rejections, it goes to the Feedback Agent.
  - If the Feedback Agent's revised attempt fails, a human gets a `risk_approval` request.

**Rules**

- No step may depend on in-memory state that is not in a checkpoint.
- The HITL log row is written before the pause, so pending requests survive restarts.

**When things fail.**

- Checkpoint write fails: stop the step and surface an error. Do not continue without a checkpoint.
- Resume finds an inconsistent state: BLOCKED plus a human.

**Scope.** MVP, all of it. Running on multiple machines comes later.

**Done when.**

- A task paused for approval survives a hard process kill and resumes correctly in **20 of 20** trials.
- The test uses deterministic ready/go hooks plus a hard kill.

**Old build.** Built, with a working crash test. The kill switch counted the wrong thing (pitfall P1).

### 5.3 Communication channels

**What and why.** In multi-agent systems, most failures come from agents passing vague text around. Here, every exchange is a typed object with a size cap, and large content travels by pointer.

**The channels**

| Channel | Written by | Read by | Rule |
|---|---|---|---|
| PhaseHandoffPacket | Outgoing phase | Incoming phase's manager | Hard token cap (table below); details by pointer |
| WorkerCoordinationPacket (WCP) | Every worker on exit, in every topology | Fan-in, the wave handoff note, Manager replan | Carries `plan_version` and `wave_index`; never a chat log or diff dump |
| ClarificationEscalation | A blocked worker | Fan-in, which batches them to the Manager | Ask RI first; the worker stops and never resumes itself |
| FeedbackReport | Validator, MASC, QA, after rejecting a finished output | Producer or Feedback Agent | Specific gaps, never "try again" |
| ReplanContext | Fan-in or the Feedback Agent | The Manager | Completed waves are frozen; carries open questions so they aren't asked twice |
| WaveHandoffNote | Fan-in, with no LLM | Next wave's workers | ≤ 2,000 tokens; dropped items become pointers |
| Blackboard | Anyone | Anyone, by pointer | `store`, `retrieve`, `exists`; a failure escalates and never returns empty content |
| HITL log, queue, history | Approval gates, timeout job | UI and humans | Log row written before the pause |
| Events and traces | Every step | UI, audit, evaluation | Observation only |
| messages | Humans and the system | Humans and the system | **Never** an agent-to-agent bus |

**Handoff token caps (§B.5)**

| Transition | Max tokens |
|---|---|
| Requirements → Design | 2,000 |
| Design → Implementation Manager | 3,000 |
| Design → each subtask | 1,500 |
| Wave → wave (WaveHandoffNote) | 2,000 |
| Implementation → QA | 2,000 |
| QA → Deployment | 1,000 |
| Any → HITL | 3,000 |

**What it looks like**

```text
WorkerCoordinationPacket
  subtask_id, worker_id, plan_version, wave_index
  assumptions [string]                 what the worker believed true
  discovered_dependencies [string]     symbols/files touched beyond assigned scope
  interface_changes [{symbol: symbol_id, before, after}]
  risks [string]
  touches_files [path]                 authoritative for overlap detection
  confidence number 0–1
  needs_manager_attention bool
  blocked bool                         true → see ClarificationEscalation
  artifact_refs [pointer]              diff, logs
```

```json
{
  "subtask_id": "A", "worker_id": "w-a-1", "plan_version": 1, "wave_index": 0,
  "assumptions": ["users table has no soft-delete column today"],
  "discovered_dependencies": ["db/models/user.py::User"],
  "interface_changes": [{"symbol": "db/models/user.py::User", "before": "no deleted_at",
                          "after": "deleted_at: timestamp | null"}],
  "risks": ["existing unique index on email ignores deleted rows"],
  "touches_files": ["db/migrations/0042_user_soft_delete.sql"],
  "confidence": 0.86, "needs_manager_attention": false, "blocked": false,
  "artifact_refs": ["T-123/diff/7f3e…", "T-123/log/9a1c…"]
}
```

```text
ClarificationEscalation
  escalation_id, subtask_id, worker_id
  category: missing_context | broken_assumption | interface_conflict | scope_ambiguity
  question string
  evidence_refs [pointer]              what RI returned, if anything
  proposed_default string ?            the worker's best guess; never auto-applied
  confidence number
  ri_consulted bool                    must be true except for pure scope ambiguity
  created_at, resolved_at?
  resolution: redispatched | hitl_resolved | superseded ?

FeedbackReport
  loop_id (e.g. FL-04), failed_agent, failure_type
  validator_findings [obj]
  specific_gaps [string]               exactly what to fix
  suggested_approach string ?
  attempt_number int

ReplanContext
  task_id, attempt_number
  previous_decomposition, previous_plan, previous_topology_decision
  completed_wave_indices [int]         frozen; never re-planned
  previous_assumptions [string]; validator_findings [obj]; wcp_summaries [string]
  unresolved_clarifications [ClarificationEscalation]
  prior_manager_decisions [string]; affected_worker_ids [string]
  repo_discoveries [string]; discovered_edges [SDG edge]; unresolved_risks [string]

WaveHandoffNote                        built by Fan-in: union → dedup → priority-truncate
  task_id, plan_version, covers_waves [int], for_wave int
  interfaces_changed [{symbol_id, before, after, by_subtask}]
  files_touched [path]; discovered_dependencies [string]
  constraints_for_next_waves [string]; unresolved_issues [escalation_id]
  artifact_refs [pointer]; token_budget int (2000); truncated bool

Blackboard
  store(task_id, kind, content) → pointer "{task_id}/{kind}/{uuid}"
  retrieve(pointer) → content          raises on missing; never returns ""
  exists(pointer) → bool
```

**Authority (§D.9.5)**

| Action | Phase manager | Wave Scheduler | Worker |
|---|---|---|---|
| Decompose, replan, reassign | Yes | No | No |
| Dispatch workers | No | **Yes (the only one)** | No |
| Emit a WCP or an escalation | No | No | Yes |

**Coordination only when needed.**

- There is one batched Manager pass per wave, and only if something was flagged: an escalation, `needs_manager_attention`, or a conflict.
- Otherwise there is no coordination step at all.

**Rejected on sight (§D.9.7)**

- Worker-to-worker messages, sent directly or through a shared object that both workers poll.
- Swarms.
- Debate as a default mechanism.
- Always-on coordination meetings.
- Recursive worker spawning.
- An LLM "merge resolution" agent.
- Using `messages` as an inter-agent bus.

**When things fail.**

- A Blackboard read fails: escalate. The caller never receives empty content.
- A handoff exceeds its cap: truncate by priority and set `truncated=true`, leaving pointers for the dropped items.

**Scope**

- **MVP:** all schemas, the Blackboard, and the caps.
- **Simplify:** the ReplanContext can start with `previous_decomposition`, `validator_findings`, and `unresolved_clarifications` only.

**Done when.**

- Schema tests cover every channel.
- A test proves no worker can dispatch.
- A test proves no step reads events for routing.

**Old build.** Schemas existed on paper; there was no Blackboard.

### 5.4 Human approvals and clarifications (HITL)

**What and why.** Humans approve irreversible actions and answer questions the repo can't answer. Every human pause must be typed, durable, and auditable, and must never auto-approve.

**What it looks like**

```text
HITLRequest
  request_id
  request_type: clarification | approval | policy_review | risk_approval
  phase, reason
  evidence_ref pointer                 the evidence bundle; not inlined
  options [string]
  response?, responded_by?, responded_at?
  timeout_at

ApprovalGate config
  checkpoint: scope | design | security | release | pr | deployment
  decisions: approve | reject_with_feedback | request_changes
  evidence_bundle_spec: which artifacts to show
  applies_when: rule (from the workflow profile)
  timeout_minutes: 60
```

| Request type | Used for |
|---|---|
| clarification | An open requirements question, from the Requirements Analyst |
| approval | An approval-gate checkpoint |
| policy_review | A human must sign off on a *routing* decision itself |
| risk_approval | An escalation that doesn't map to a normal checkpoint. Examples: the Feedback Agent's revised attempt also failed, the global loop guard tripped, or the step-visit ceiling was hit |

| Checkpoint | Pauses in phase |
|---|---|
| scope | requirements |
| design | design |
| security | design |
| release | qa |
| pr | review |
| deployment | release |

**How it works (lifecycle)**

- **On pause:**
  1. Build the request with an explicit `request_type`.
  2. Insert the durable log row (`responded_at` empty), idempotently.
  3. Add it to the in-run queue.
  4. Pause.
- **On resume:**
  1. Update the log row with the response, the responder, and the time.
  2. Remove it from the queue.
  3. Append it to the history.
  4. Route on the decision.
- **On timeout (fail closed):**
  - A scheduled job finds expired rows and sets status `timeout_escalated` by `system:timeout`.
  - It notifies a human.
  - It **never auto-approves**.
  - `responded_at` stays empty, so the item stays in the pending inbox.
- **The pending list reads the durable log**, not the in-run queue, so it survives restarts.

**Approval permissions (§S)**

| Action | developer | reviewer | deployer | admin |
|---|---|---|---|---|
| Submit task, view, answer clarifications | ✓ | ✓ | ✓ | ✓ |
| Approve scope, design, release, staging deploy | ✗ | ✓ | ✓ | ✓ |
| Approve production deploy, trigger rollback | ✗ | ✗ | ✓ | ✓ |
| View cost, suspend tasks, change risk thresholds | ✗ | ✗ | ✗ | ✓ |

**Rules**

- The production deployment gate always fires, regardless of confidence or policy rule.
- A human approves every merge. The only exception is Rule 4 auto-merge (5.10), which needs all three: low risk, full QA green, and confidence above the auto-merge ceiling.
- A gate fires only if the workflow profile lists it **and** its phase is running.
- Every decision is stored with the approver and an evidence pointer.
- `reject_with_feedback` and `request_changes` both send the work back to the producing phase with a FeedbackReport built from the human's text.
  - `reject_with_feedback` means the approach is wrong; the phase manager re-plans.
  - `request_changes` means the approach is right but specific fixes are needed; the producer revises.

**When things fail.** The UI is down or nobody responds: the task holds and the escalation chain notifies. The run never proceeds.

**Scope**

- **MVP:** 3 gates — scope, design, and PR/merge.
  - The release gate is **folded into the PR gate**: the PR gate shows the full QA evidence bundle (decision D6).
  - The deployment gate is added together with the release phase, and from then on it always fires for production.
- **Later:**
  - a separate release gate
  - the security gate (critical risk, design phase)
  - policy_review requests

**Done when.**

- Every approval goes through the inbox.
- The timeout job runs on a schedule and is tested.
- No code path auto-approves.

**Old build.** The gate template and log were built. The timeout job was registered but **never scheduled** (pitfall P2).

### 5.5 Intake and planning

**What and why.** This phase turns a raw request into a classified Task, with risk, type, and repo refs, so that every later rule has inputs.

**How it works**

1. The Planning Manager makes one fast-tier call. Its input is the request text plus the architecture summary. Its output is `{type, methodology, risk_tier, repo_refs, title}` as validated structured output.
2. The platform builds a `WorkflowContext` (5.10).
   - Unknown booleans stay *unknown* (null); they are not false.
   - Repo scale comes from the RI file count. Unknown counts as medium.
3. The platform attaches a `WorkflowProfile` (MVP: most conservative) and the default budget.
4. The platform computes the confidence score if inputs exist; otherwise it stays null (5.7).
5. The task moves to `requirements`.

**When things fail.** Classification fails twice: create a HITL clarification asking a human to classify. Never default to "low risk".

**Scope**

- **MVP:** classification, context, profile, budget.
- **Later:** the Intent Tracker, which detects the user changing intent mid-task. It is an extra LLM; skip it for now.

**Done when.** Every intake logs a classification and a confidence value, or an explicit null.

**Old build.** Partial. The Planning Manager existed; confidence was never written (pitfall P7).

### 5.5a Bug reproduction (bug and hotfix tasks only)

**What and why.** Never fix a bug you haven't reproduced. A fix for a misunderstood bug is worse than no fix.

**How it works**

1. The step runs at the end of the requirements phase, after the scope gate and before any design or fix.
2. The Bug Validation Agent writes a reproduction (a failing test or script) and runs it in the sandbox.
3. **If it reproduces:**
   - Store the reproduction on the Blackboard.
   - Add it to the acceptance criteria: "the reproduction passes".
   - Continue to the next phase.
4. **If it doesn't reproduce:**
   - Send a HITL `clarification`: "Not reproducible as reported", with what was tried.
   - The human adds detail, which re-runs this step at most once, or closes the task.
5. QA re-runs the stored reproduction after the fix. It must pass.
6. The reproduction becomes a committed regression test (5.12).

**Scope.** Later, but it is the first QA-side feature to add once bug tasks are in use.

**Done when.** No bug or hotfix task reaches implementation without a stored reproduction or a human override.

### 5.6 Requirements engine (evidence first)

**What and why.**

- **Problem:** requirements interviews waste human time on things the repo already answers ("what database do you use?").
- **Approach:**
  - Turn the request into typed claims.
  - Answer what the repo can answer, with evidence.
  - Ask humans only the rest, ranked by value, one question at a time.
  - Exit through a deterministic gate.

**How it works**

```text
1  EXTRACT    one LLM call, no repo access  → ClaimSet
              2 attempts; then empty ClaimSet with extract_failed=true
2  SNAPSHOT   cheap repo facts: manifests (allowlist, ≤32 KiB each), architecture summary,
              ≤40 services, ≤5 entry points, ≤5 key symbols, ≤20 paths, top-20 repo map
3  CLASSIFY   fill WorkflowContext flags from claims (unknown stays null)
4  ACTIVATE   question bank → active slots via applies_if predicates; order via depends_on (DAG)
5  SEED       fill slots the request already decided (source = "request")
6  RETRIEVE   run each open slot's evidence plan against RI → EvidenceRecords
7  AUTO-ANSWER  answer a slot from evidence when the plan says it is safe
8  RANK       score remaining slots
9  ASK        one question to the human; record the answer (source = "human")
10 SUFFICIENCY  gate → spec_ready | accept_gaps | needs_hitl | continue (back to 6)
```

**What it looks like: claims**

```text
Claim
  id, kind, text, status, provenance
  kind:   objective | functional | constraint | nfr | acceptance | out_of_scope | repo_dependent | unknown
  status: FACT | INFERENCE | DECISION | UNKNOWN | CONTRADICTION
  provenance { source: request | engineer | repository | derived | assumption,
               ref?, retrieved_via: snapshot | symbol | lexical | graph | semantic | manifest | none,
               catalog_hash? }
  nfr_type?
  touches_auth?, touches_pii?, touches_payments?, has_database_changes?   null = claim is silent

ClaimSet { claims [Claim], raw_request, extract_failed bool }
```

What a claim is *about* (`kind`) is independent of *how we know it* (`status`).

- A repo FACT "uses relational DB X" plus a user DECISION "use document DB Y" is **not** a contradiction. The user is choosing to change it.
- CONTRADICTION is only for two explicit *decisions* that cannot both hold.

**What it looks like: evidence**

```text
EvidenceRecord
  id, signal (snapshot | symbol | lexical | graph | semantic | manifest | none)
  query?, refs [string], excerpt?, score?, catalog_hash?, cache_hit, latency_ms?
  unavailable bool, unavailable_reason?      "source down" is not the same as "zero hits"
  accept_as: fact | inference ?             semantic hits are always inference
  ri_method?, result_count

AutoAnswer { slot_id, answer, evidence_refs [string], status: fact | inference,
             confidence: low | medium | high }
```

**What it looks like: a question-bank slot**

```yaml
- id: Qsec1
  category: security_compliance
  mandatory: true
  text: What compliance requirements apply (auth, payments, PII)?
  applies_if:
    any_true_or_unknown: [touches_auth, touches_pii, touches_payments]   # unknown counts as true
  depends_on: [Q1]
  evidence_plan:
    need: existing_auth_module
    methods:
      - {signal: snapshot, query: auth, extractor: service_exists}
      - {signal: symbol, symbol_id: "auth/service.py::AuthService", extractor: symbol_exists, budget: 1}
      - {signal: lexical, query: AuthService, extractor: identifier_in_snippet, budget: 1}
    accept_as: fact
    on_insufficient: unknown          # or ask_human
    max_ri_calls: 4
  impact: 0.95
  risk: 0.95
  information_value: 0.85
```

**Predicate keys:** `always`, `all`, `any`, `work_type_in`, `risk_tier_in`, `any_true_or_unknown`, `affected_modules_gt`, `field` + `eq` / `neq`.

**Question categories:** business_objective, functional, non_functional, security_compliance, performance, scalability, reliability, data_integrity, api_contracts, deployment_constraints.

**The 24-slot bank used before:**

| Group | Slots |
|---|---|
| Objective | Q1–Q3 |
| Stack | Qstack1 |
| Security | Qsec1–3 |
| Feature | Q4–Q6 |
| Bug | Q4b–Q6b |
| Hotfix | Q7h, Q8h |
| Integration | Qint1–3 |
| Database | Qdb_tech, Qdb1–3 |
| NFR | Qnfr1 |
| Deployment | Qdep1 |

**Ranking (deterministic, no LLM)**

```text
score = 0.35·impact + 0.25·risk + 0.25·information_value + 0.15·unresolvedness
unresolvedness = 1.0 UNKNOWN | 0.5 INFERENCE | 0.0 FACT/DECISION | 1.0 CONTRADICTION
```

- Mandatory unanswered slots are always queued, in `depends_on` order.
- Score and `asking_cost` cannot remove a mandatory slot.
- Optional slots fill the rest of a **12-question session cap**, highest score first.
- `asking_cost` is a gate for optional slots (above the limit means deferred). It is never a divisor.

**Default (impact, risk, information value) by category**

| Category | Defaults |
|---|---|
| business_objective | 0.80 / 0.40 / 0.90 |
| functional | 0.70 / 0.50 / 0.70 |
| non_functional | 0.50 / 0.50 / 0.50 |
| security_compliance | 0.90 / 0.90 / 0.80 |
| performance | 0.60 / 0.60 / 0.50 |
| scalability | 0.55 / 0.55 / 0.45 |
| reliability | 0.60 / 0.70 / 0.50 |
| data_integrity | 0.70 / 0.75 / 0.55 |
| api_contracts | 0.65 / 0.60 / 0.50 |
| deployment_constraints | 0.50 / 0.55 / 0.40 |

**Sufficiency gate.** The checks run in this exact order, and the first match wins:

1. Any CONTRADICTION → `needs_hitl`.
2. The engineer explicitly accepted the remaining gaps → `accept_gaps`.
3. Extraction failed → `needs_hitl`.
4. Repo evidence is stale or unavailable → `needs_hitl`. `spec_ready` can never fire on stale evidence.
5. No mandatory slot is open and no high-impact UNKNOWN remains → `spec_ready`.
   - High-impact unknowns are UNKNOWN claims that are not `repo_dependent`.
   - They count only while mandatory slots are open; after that they become logged assumptions.
6. Nothing left to ask, or the question budget is used up with nothing askable → `needs_hitl`.
7. Otherwise → `continue`, asking the next highest-value slot.

**Rules**

- A semantic search hit is never a FACT.
- Compliance slots close only on an explicit compliance decision. Wording about auth or JWT is not enough.
- Seeded answers are labeled `source="request"`, never "human".
- Every pipeline step emits a session event: start, extract, snapshot, classify, activate, seed, retrieve, auto_answer, rank, ask, answer, sufficiency, exit.

**Budgets**

| Budget | Value |
|---|---|
| RI calls per session | 16 |
| Semantic top-k | 3 |
| Lexical top-k | 10 |
| Inner steps | 32 |
| Run steps | 24 |

**Outputs.** A `RequirementsSpec`, a handoff packet of at most 2,000 tokens, and the claim and evidence log.

**When things fail.** Every failure exits as `needs_hitl`. The engine never proceeds on its own.

**Scope**

- **MVP:** the full pipeline, with about 10 slots.
- **Later:** the full 24 slots, and precedent from episodic memory.

**Done when.**

- It asks on at least 95% of ambiguous inputs.
- It skips at least 95% of well-specified ones.
- Both are measured on a labeled set.

**Old build.** Fully built and tested as a library, but **never called by the workflow** (pitfall P10).

### 5.7 Confidence score

**What and why.** A single number that says how sure the platform is about a phase's output. It is used for routing (more checks or fewer), **never** to unlock irreversible actions.

**Formula (§B.4)**

```text
confidence = 0.35 × retrieval_coverage        how much of the needed evidence was found
           + 0.20 × precedent_strength        similar past tasks succeeded (needs episodic memory)
           + 0.30 × validator_agreement       independent validators passed
           + 0.15 × static_check_cleanliness  lint/type/SAST clean
```

**Floors and what happens below them**

| Phase | Floor | Below the floor |
|---|---|---|
| Requirements | 0.80 | The sufficiency gate decides when questioning ends (5.6). Confidence is computed after that. If it is below 0.80, the scope gate shows a "low confidence" flag, and the human chooses between more questions and approval (decision D14) |
| Design | 0.85 | Return to the architect |
| Implementation | 0.75 | Upgrade the model tier |
| QA | 0.90 | Block deployment |
| Deployment | 0.95 | Always a human anyway |

**Rules**

- A missing input or a calculation error means the score is null, and null is treated as below every floor.
- Topology rule TP-02 uses its own threshold of **0.70**. Never merge it with the 0.75 implementation floor.
- The weights are starting values only.
  - First run a drop-one ablation, because `retrieval_coverage` and `validator_agreement` may overlap.
  - Then recalibrate on shadow-mode outcomes, for example with logistic regression.

**Scope**

- **MVP:** two signals, validator agreement plus static cleanliness, renormalized. Record which signals were used.
- **Later:** all four signals.

**Done when.** A score, or an explicit null, is logged at every intake and every phase exit.

**Old build.** The formula existed but was never written to the task (pitfall P7).

### 5.8 Implementation engine: decomposition, waves, workers, and Fan-in

**What and why.**

- **Goal:** turn an approved design into merged code, running independent work in parallel *safely*.
- **Separation:** the LLM decides *what* to build. Deterministic code decides *when* each piece runs and *how* results merge. That keeps the risky part, parallel edits, auditable and testable.

#### 5.8.1 Flow

```text
1  DECOMPOSE   Implementation Manager — ONE structured LLM call, no tools
               input: approved ArchitectureDoc + architecture summary + handoff packet
               output: TaskDecomposition (WHAT)
2  PLAN        plan_execution_waves() — deterministic, same step, no LLM
               output: ExecutionPlan + TopologyDecisionRecord (WHEN)
3  DISPATCH    Wave Scheduler — one worker per subtask in the current wave
4  WORK        CodeGen worker in its own git worktree → diff + WCP, or ClarificationEscalation
5  VALIDATE    Validator(implementation) per branch — tools only, no LLM
6  FAN-IN      deterministic merge after every wave (10 steps below)
7  REPEAT      3–6 for each wave
8  INTEGRATE   Integration Validator — once per attempt, on the merged result
```

#### 5.8.2 Data shapes

```text
TaskDecomposition
  tasks [{ id, description, module, target_files [path], declared_dependencies [id], model_tier_hint? }]
  ownership_map { module_path: subtask_id }
  version int                           +1 on every Manager replan
  (no scheduling field — the planner ignores any)

SDG edge (SubtaskDependencyEdge)
  from_subtask, to_subtask              from must finish before to
  kind: produces_interface | file_overlap | symbol_overlap | shared_resource
      | build_order | test_coupling | declared | discovered
  blocking bool                         true forces ordering; false is advisory
  evidence string                       RI query + result digest, or WCP/escalation id
  source: manager_declared | repo_intelligence | runtime_discovery
  confidence number                     1.0 for deterministic facts

SubtaskDependencyGraph { nodes [id], edges [edge], plan_version, ri_available bool }

ExecutionWave  { wave_index, subtask_ids [id], width, rationale }
ExecutionPlan
  plan_version, task_id, waves [ExecutionWave]
  topology_class: sequential | parallel | hybrid      derived, never an input
  max_wave_width int                    policy cap applied
  dispatch_concurrency int              runtime cap ≤ max_wave_width; never changes waves
  dependency_graph SDG
  created_from: initial_plan | amendment | replan
  superseded_plan_version?

TopologyDecisionRecord                  one per plan_version; audit + evaluation input
  decision_id, task_id, plan_version, topology_class, subtask_count, wave_count
  widths [int], blocking_edge_count, advisory_edge_count, unverified_edge_count
  features {..}                         snapshot of the inputs used
  policy_rules_fired [string]           e.g. ["TP-08"] or ["TP-03"]
  width_cap_source string               "final=2|profile=2|ctx=5|hard=none|soft=TP-08:4"
  fail_closed_reason?, created_from, created_at

ImplementationResult                    append-only; never rewritten
  subtask_id, worker_id, attempt_number, plan_version, wave_index
  diff_ref pointer, touches_files [path]
  status: validated | blocked | failed
  merge-eligible ⇔ status = validated AND (subtask_id, plan_version, attempt_number) ∉ demotion_ignore_keys
```

#### 5.8.3 The wave planner: `plan_execution_waves()`

```text
Step 1  Seed the SDG from the Manager's declared dependencies (kind=declared, blocking=true)
Step 2  Verify and augment with RI (≤ 50 RI calls per plan):
          confirm or refute declared edges; add file_overlap, symbol_overlap,
          produces_interface, shared_resource edges.
          Pairs not checked within budget → a blocking edge with evidence "unverified: RI budget"
          and confidence 0 (fail closed; counted in unverified_edge_count) — decision D15.
          Cycle found → no plan is dispatched; Manager replans.
Step 3  Compute max_wave_width from the TP rules (below)
Step 4  Levelize: level 0 = no blocking predecessors; level k = latest predecessor in level k-1.
          Within a level, order by HLF (highest level first = longest remaining critical path).
Step 5  Split any level wider than max_wave_width into consecutive waves (keeps HLF order;
          splits never invent edges)
Step 6  Derive topology_class; write ExecutionPlan + TopologyDecisionRecord
```

**Topology rules (TP).** These are configuration in a policy file, never an LLM.

- **Hard gates** run in order. The first match forces width 1 and stops.
- **Soft caps** all apply. The smallest wins, and the result can never exceed the profile bound.

| Rule | Kind | Condition | Width |
|---|---|---|---|
| Pre-gate | hard | `profile.execution_order == sequential` (e.g. hotfix) | 1 |
| TP-01 | hard | RI unavailable | 1 |
| TP-02 | hard | Confidence is null or below 0.70 | 1 |
| TP-03 | hard | Critical risk | 1 |
| TP-04 | hard | Small repo (under 1k files; unknown size does **not** fire) | 1 |
| TP-05 | soft | High risk | 2 |
| TP-06 | soft | At least one *blocking* `shared_resource` edge | 2 |
| TP-07 | soft | Blocking-graph height ≥ 5 | 3 |
| TP-08 | soft | Always, when no hard gate fired | `ceil(√n)` if n ≥ 8 subtasks, else 4 |

```text
profile_bound        = min(profile.max_parallelism, ctx.max_parallel_impl_agents)
max_wave_width       = 1 if a hard gate fired else min(profile_bound, matching soft caps)
dispatch_concurrency = min(max_wave_width, free workers, budget-allowed workers)   runtime only

topology_class:
  all widths == 1                → sequential
  no blocking edges              → parallel   (even if a width split made several waves)
  exactly one wave               → parallel
  otherwise                      → hybrid
```

- **Repo-scale caps (`max_parallel_impl_agents`):** small 2, medium 3, large 5, enterprise 8. Unknown size counts as medium.
- **The TP rules may only:**
  - lower the width
  - force width 1
  - cause Step 5 to split a level
- **The TP rules may never:**
  - remove a blocking edge
  - invent subtasks
  - call an LLM
  - raise the width above the profile bound
- **Not configurable:**
  - "RI unavailable → width 1"
  - "amendments never widen"

#### 5.8.4 Worker (CodeGen) loop

**Input** (assembled by the context builder, 5.16):

- the subtask spec (≤ 1,500 tokens)
- the architecture summary
- a repo map seeded on this subtask's target files (1,500–2,500 tokens)
- the pinned ledger entries
- the latest WaveHandoffNote
- skeletons (signatures only) of candidate files
- full bodies of the precise edit locations only

**Loop**

```text
repeat until done or limits hit:
  response = model.call_tools(prompt, tools)          tools: section 7.2 worker set
  for EACH tool call in the response (not just the first):
      platform validates args → executes in the worker's worktree / sandbox → caps output
      append result to the conversation
  after any write tool: RI.reindex_paths(changed paths)
before finishing: run_checks(changed files) must be clean, or report why not
final output (structured): diff summary + WCP     or     ClarificationEscalation + stop
```

**Rules**

- No raw shell and no network by default.
- Writes are allowed only under the worker's worktree.
- Workers never spawn sub-agents. A subtask that is too big raises `scope_ambiguity`, and the Manager splits it.
- **Limits** (starting values from section 12):
  - 25 tool turns per worker
  - 4,000 tokens per tool result; the rest is offloaded to the Blackboard
  - 15 minutes of wall time per worker
  - Hitting a limit makes the worker stop with a `ClarificationEscalation(category=scope_ambiguity)`. It never ends silently.

#### 5.8.5 Git isolation

| Thing | Value |
|---|---|
| Worktree path | `{repo_root}/.sdlc/worktrees/{task_id}/{subtask_id}/` |
| Branch name | `sdlc/{task_id}/{subtask_id}` |
| Base for wave 0 | `task_base_sha` |
| Base for later waves | Current integration HEAD, which includes the merged earlier waves |

- A superseded attempt's worktree is deleted.
- Code rollback means discarding the branch.

#### 5.8.6 Fan-in Coordinator

Fan-in is deterministic and runs after every wave. Its ten steps, in order:

1. Pick the latest merge-eligible result per subtask.
2. Check file overlap within the wave, using WCP `touches_files` cross-checked against the diff.
3. Check semantic conflicts within the wave, using WCP `interface_changes`, `assumptions`, and RI callers.
4. Check compatibility with earlier, already-merged waves.
5. Merge the clean branches.
6. Demote conflicting branches (the state machine below).
7. Amend the plan with newly discovered blocking edges.
8. Trigger at most **one** Manager replan per wave, with batched escalations in a ReplanContext.
9. Build the WaveHandoffNote: union, deduplicate, truncate by priority to 2,000 tokens.
10. Advance to the next wave or exit.

**Wave demotion (S1–S7)**

| Step | Action |
|---|---|
| S1 | Freeze the conflicting branches; merge their clean siblings first |
| S2 | Mark the conflicting attempts superseded (add them to `demotion_ignore_keys`) and delete their worktrees |
| S3 | Order the conflicting subtasks by evidence, then by subtask id. A cycle aborts to a Manager replan |
| S4 | Amend the plan, rewriting the active plan; no live `[A,B] + [B]` |
| S5 | Record a `wave_demotion` event |
| S6 | Redispatch with `attempt_number + 1` |
| S7 | Continue |

**Amendments**

- They only add blocking edges and never widen the width.
- At most **3** per attempt (`max_plan_amendments`). After that, the Manager replans.
- Completed waves are never re-planned or unmerged.

**When things fail**

| Failure | Behavior |
|---|---|
| Topology selection can't complete safely | Run everything sequentially |
| A plan contains a cycle | Never dispatch it; the Manager replans |
| RI fails during the semantic cross-check | Treat as a conflict: demote if 2+ branches are involved, else replan |
| A worker crashes | Idempotent retry under the same key |

**Scope**

- **MVP (simplified):**
  - Parallel only when subtasks touch disjoint files.
  - Maximum width 2.
  - On any conflict, rerun the conflicting subtasks one after another.
  - Keep the data shapes and the TopologyDecisionRecord.
- **Later:**
  - the full TP-01..TP-08 rules
  - S1–S7 demotion
  - amendments

**Done when**

- **MVP unit tests:**
  - the topology class derivation
  - a cycle is rejected
  - width never exceeds 2
  - overlapping files are never in the same wave
  - `merge_eligible` is never true for ignored keys
- **Later unit tests:**
  - each TP rule
  - amendments ≤ cap and add-only
  - demotion rewrites the active plan
- **Integration test:** two subtasks with zero file overlap but an interface conflict are caught at Fan-in.
- **Call-count test:** a happy-path span count of 1 Manager + N workers + 1 Integration Validator.
- **Quality bar:** at least 80% first-pass static-check success for low and medium risk.

**Old build.** Docs only.

### 5.9 Validators, output checks, and structured outputs

**What and why.** Every agent output is checked by something independent of the producer before it moves on. Most checks are tools, not LLMs.

**How it works**

- **The Validator template.**
  - Config: which phase, which checklist or tools, and pass rules.
  - Output: pass/fail plus findings.
  - On fail, it emits a FeedbackReport to the producer.
  - `Validator(implementation)` is tools only: lint, type, SAST.
- **MASC (post-step checker).** It runs after every agent step, in this order:
  1. **Schema check:** the output matches its declared schema.
  2. **Confidence check:** the self-reported or computed confidence is at or above the floor.
  3. **Semantic drift check:** the output still addresses the task's intent.
  - Results become `ValidationFlag`s. A critical flag triggers FL-10.
- **Structured outputs everywhere.**
  - Every agent has a declared output schema, validated at runtime.
  - An agent never returns free text where structure is expected.
  - An unparseable output is a schema violation, never "best effort".
- **Reflection pass.** Only the Design Manager and the Security Architect get one. It is one extra call listing missed requirements, contradictions, and hidden assumptions.

**Rules**

- A validator never shares a model call with its producer.
- Assert on structure, never on LLM wording.

**Scope**

- **MVP:** the schema check plus validators.
- **Later:** the semantic drift check. It can be cut until there is data showing it adds value.

**Done when.** Every agent output passes through schema validation; this is tested by injecting a malformed output.

**Old build.** The templates were built. The drift check was a stub that always said "not checked" (pitfall P8).

### 5.10 Workflow policy: context, profile, rules, and agent selection

**What and why.** This is deterministic logic that decides, per task, which agents run, which approvals fire, how deep QA goes, which model tier to use, and how much parallelism is allowed. It is what makes the platform "dynamic" without an LLM deciding.

**What it looks like**

```text
WorkflowContext                         input; unknown = null, never false
  work_type, methodology, risk_tier, confidence_score?
  repo_architecture, repo_scale: small (<1k) | medium (<10k) | large (<100k) | enterprise (100k+)
  affected_module_count, dependency_fan_out
  touches_shared_infra?, has_database_changes?, has_api_contract_changes?, has_ui_changes?, is_greenfield?
  production_criticality: low | medium | high | critical
  requires_backward_compat?, has_external_consumers?
  derived: requires_full_design_phase = greenfield OR type ∈ {migration, new_project}
                                        OR (risk ∈ {high, critical} AND touches_shared_infra)
  derived: max_parallel_impl_agents = {small:2, medium:3, large:5, enterprise:8}[scale], default 3

WorkflowProfile                         output
  agent_set [string]
  execution_order: sequential | parallel_where_independent
  qa_depth: minimal | standard | deep | exhaustive
  model_tier: fast_cheap | balanced | frontier
  approval_requirements [scope | design | security | release | pr | deployment]
  max_parallelism int
  cost_budget_usd number
  topology_policy_id string = "default"
```

**The most conservative profile.** This is the MVP default for every task.

| Field | Value |
|---|---|
| agent_set | all agents on |
| execution_order | parallel_where_independent |
| qa_depth | standard |
| model_tier | balanced |
| approvals | scope, design, release, pr, deployment |
| max_parallelism | 2 |
| cost_budget_usd | 20.0 |

At MVP, the `release` approval is satisfied by the PR gate, because the release gate is folded into it (5.4, decision D6).

**When the profile is resolved**

- **At intake.** Confidence is usually null then, so Rule 3 fires and the profile stays conservative.
- **Once more at requirements exit,** when confidence exists, before the scope gate.

Both results are stored in a `policy_decision` record: rule fired, inputs, profile. A re-resolution may loosen the profile only through an explicit rule.

**Policy rules (later, §F.3).** Rules are ordered and the first match wins. **Each rule sets its complete approval list**; it never appends to or edits a base list (pitfall P19).

| # | When | Approvals (complete list) | Other settings |
|---|---|---|---|
| 1 | Critical risk | scope, design, security, release, pr, deployment | QA exhaustive; model frontier |
| 2 | Hotfix to production | scope, pr, deployment | Execution sequential; QA standard; Bug Validation on; full design skipped |
| 3 | Confidence null or below 0.80 | scope, design, release, pr, deployment | QA standard; model balanced |
| 4 | Low risk **and** confidence above the auto-merge ceiling | deployment (production only) | Auto-merge allowed; model fast_cheap |
| 5 | Risk medium or high (the default path) | scope, design, release, pr, deployment | QA standard (deep for high); model balanced |
| 6 | Low risk, not auto-merge eligible | pr, deployment | QA minimal; model fast_cheap |

- The rules cover every risk tier.
  - Critical always matches Rule 1.
  - Low risk matches Rule 4 or Rule 6, unless Rule 2 or 3 matches first.
- Rule 5 is the "risk ≥ medium" condition, written as an explicit rule (decision D6).

**Model-tier escalation.** It returns a decision object `{tier, route}`, never just a tier (pitfall P18).

| Validator rejections on the same step | Decision |
|---|---|
| 1 | Same tier; retry with the FeedbackReport |
| 2 | Up one tier (fast_cheap → balanced → frontier; frontier stays frontier); retry |
| 3 (`max_retries_per_node`) | Route to the Feedback Agent with a ReplanContext |
| The Feedback Agent's revised attempt also fails | Route to a human as `risk_approval` |

The rejection counter resets when the Feedback Agent issues new instructions (decision D8).

**Agent selection (§F.4)**

| Condition | Adds | Skips |
|---|---|---|
| Hotfix | Bug Validation, Rollback agent | Full design phase, Security Architect |
| Risk ≥ medium | Security QA (SAST) | — |
| High risk | Performance QA, exploratory QA | — |
| Low risk | — | Mutation, exploratory, performance |
| DB changes | Migration Validator | — |
| API changes | API Contract Validator, Consumer Notification | — |
| UI changes | UI QA, Accessibility QA | — |
| Enterprise repo | Shard Coordinator | — |
| Greenfield | Architecture Decision Agent | Regression analysis (no history yet) |
| Waterfall | Stage Gate Enforcer | — |
| Shared infrastructure | Security Architect (forced on, even for a hotfix) | — |

Every agent named here appears in the roster (4.2), with its tier and tools (decision D11).

**Rules**

- Every pair of policy rules has a test proving they don't overlap.
- Every risk × work type × confidence combination is tested.
- No agent hard-codes a shortcut. Everything reads the profile.

**Scope**

- **MVP:** the most conservative profile only.
- **Later:** rules 1–5, escalation, and agent selection.

**Done when.**

- There is at least 90% agreement with a human architect on a labeled set.
- The full combination matrix passes.

**Old build.** Docs only.

### 5.11 Feedback loops and retries

**What and why.** Every backward edge in the lifecycle is a *named* loop with a cap. That keeps loops finite and measurable. All loops live in one registry, not scattered in agent code.

| Loop | Trigger | Returns to | Max | Needs a human |
|---|---|---|---|---|
| FL-01 | Requirements gaps | Requirements Analyst | Unlimited (bounded by question cap) | No |
| FL-02 | Design checklist fails | Design Manager | 5 | No |
| FL-03 | Design finds a requirement gap | Requirements | 1 | Yes |
| FL-04 | Static analysis fails | CodeGen worker | 3 | No |
| FL-05 | Integration fails | Implementation Manager | 2 | No |
| FL-06 | Any of: Spec QA fails, a real test fails, a critical non-security QA finding | Implementation | 3, shared across all its triggers | No |
| FL-07 | QA finds a design defect | Design | 1 | Yes |
| FL-08 | Critical security finding | Design | 1 | Yes |
| FL-09 | Canary health delta over 15% (owner: Monitoring Manager) | CI/CD rollback, then BLOCKED for a human | Auto | No, for the rollback itself |
| FL-10 | MASC critical anomaly | Previous checkpoint | 1 | Yes |
| FL-11 | Intent contradiction | Requirements | 1 | Yes |

**How it works**

- Each trigger creates a FeedbackReport and a `feedback_loop_events` row: loop id, source, target, attempt, resolved.
- Any replan builds a ReplanContext, so each attempt is better informed than the last.
- **Global guard:** when `rollback_count ≥ max_retries_per_node × active_phases`, suspend the task, keep its full state, and notify a human.

**Scope**

- **MVP:** five loops — requirements gaps, design fails, static check fails, tests fail, human rejects.
- **Later:** the rest.

**Done when.**

- Each loop has a test for its cap.
- The global guard has a test.

### 5.12 QA

**What and why.** Prove the change works, is safe, and matches the requirements, using deterministic tools wherever possible.

**Activation matrix (§K.1)**

| Check | Runs when | Needs an LLM |
|---|---|---|
| Lint / type | Always | No |
| Secrets scan | Always | No |
| Dependency vulnerabilities | Always | No |
| Unit and integration tests (impact-scoped) | Always | No |
| Spec QA (requirement coverage) | Always | **Yes** |
| SAST, inline | Risk ≥ medium | No |
| Deep dataflow security | Risk ≥ high, periodic | No |
| License / supply chain | Risk ≥ medium | No |
| API contract fuzzing | API contract changes | No |
| Mutation testing | Risk ≥ high, critical-path modules only | No |
| Property-based tests | Risk ≥ medium, pure functions | No |
| Exploratory testing | Risk ≥ high, UI changes | **Yes** |
| Performance | Risk ≥ high, performance-sensitive path | No |
| Accessibility | UI changes | No |
| DAST | Production criticality = critical | No |

13 of the 15 checks use no LLM.

**QA depth** (`WorkflowProfile.qa_depth`) decides which rows run:

| Depth | Runs |
|---|---|
| minimal | The "Always" rows only |
| standard | The "Always" rows, plus every row whose condition matches |
| deep | standard, plus mutation and property tests on the touched modules even below their risk condition |
| exhaustive | deep, plus the full test suite, plus deep dataflow security on every run |

**How it works**

1. **Test-impact analysis.**
   - Run tests that touch the changed code plus its dependents, using the RI impact set (and the test-to-code map, section 6.10).
   - Run the full suite only at `exhaustive` depth (critical risk) or when explicitly asked.
2. **Bug reproduction re-run** (bug and hotfix tasks).
   - The reproduction stored in 5.5a must now pass.
   - Its result is shown first in the evidence bundle.
3. **Regression tests after QA passes.**
   - The QA Manager dispatches one CodeGen worker run, the regression test writer, in its own worktree. It writes tests for each found bug and edge case, plus the bug reproduction.
   - QA agents themselves never get edit tools.
   - Metadata: `{test_id, covers_requirement_id, covers_module, generated_by_task_id}`.
   - The failure pattern `{module, failure_type, fix_pattern}` goes to episodic memory.
4. **Evidence bundle.** It is attached to the PR and stored on the Blackboard.

**What it looks like**

```text
QAEvidence
  static_analysis {..}?; security_findings [obj]; mutation_score?; property_violations [obj]
  exploratory_findings [obj]; spec_compliance {..}; coverage_delta?; risk_score
  recommendation: pass | pass_with_warnings | fail

Evidence bundle (§K.5): coverage delta, static results (severity counts), security findings
  (severity breakdown), mutation score (if run), test results (pass/fail/skip),
  spec compliance report, bug reproduction result (bug/hotfix), risk score at QA entry
```

**Scope**

- **MVP:** lint/type, tests, SAST, secrets, Spec QA, impact-scoped selection.
- **Later:** the rest of the matrix.

**Done when.** QA catches at least 95% of seeded defects on a benchmark.

### 5.13 Review, release, and monitoring

**What and why.** Changes land safely, through the team's existing processes and with no standing production access.

**How it works**

- **Review.**
  - The Review Manager checks the diff against the design, standards, and QA evidence.
  - It opens a PR with the evidence bundle.
  - "Changes requested" goes back to implementation.
- **Merge rules.**
  - Agents never push to protected branches.
  - Auto-merge happens only when all three hold:
    - risk is low
    - the full QA suite is green
    - confidence is above the auto-merge ceiling
  - Otherwise a human merges.
- **Release.**
  - The Release Manager picks a strategy (rolling, blue-green, or canary) and triggers **existing CI/CD**.
  - It never calls cloud APIs directly.
  - The production deploy gate always fires.
- **Monitoring.**
  - A bake-in period compares canary health against the baseline.
  - Thresholds: auto-promote under 5% delta; human review at 5–15%; roll back over 15%.
  - An incident creates a new task linked by lineage.

```text
DeploymentRecord
  strategy: rolling | blue_green | canary; target_env; pipeline_run_id?
  canary_metrics { error_rate_delta, p99_latency_delta, saturation_delta }?
  health_status: healthy | degraded | failed ?; rollback_triggered bool; deployed_at?
```

**Scope**

- **MVP:** PR creation plus the PR gate.
- **Later:** release, canary, and monitoring.

**Done when.** There are zero agent commits on a protected branch without approval or a passing auto-merge check.

### 5.14 Integrations

**What and why.** Connect to a git host (PRs, comments), a ticket system (import tasks), chat (notifications), and CI/CD (deploys).

**Rules**

- One adapter interface per integration type, so the provider can be swapped.
- Every external call carries an **idempotency key**, so retries never create duplicate PRs or comments.
- Credentials are least-privilege and task-scoped.
- Issue, PR, and comment text is **untrusted input** (5.18).

**Scope**

- **MVP:** the git host only.
- **Later:** chat, then tickets.

**Done when.** A real ticket becomes a human-approved PR with no manual re-entry.

### 5.15 Model layer

**What and why.** The platform talks to models only through one interface, so providers and models can be swapped without workflow changes, and cost is always known.

**What it looks like**

```text
ModelAdapter
  complete(request) → response
  stream(request) → chunks
  call_tools(request, tools) → response with zero or more tool-call requests
  embed(texts) → vectors
  pricing → { input_per_1k, output_per_1k, version, effective_date }
  capability_score → 1–10
  (async versions of each)

ModelRouter.pick(phase, operation, risk_tier) → model
  cheapest model whose capability_score ≥ required(phase, operation)
  high/critical risk adds +1 to the requirement
  old scores: cheap tier 6, strong tier 9
```

**Rules**

- No provider SDK import outside the adapter package. Enforce this with an import-boundary test.
- Cost comes from **your own pricing registry**, versioned and dated, never from the provider's reported cost.
- A free model still gets a non-zero internal price, so the kill switch sees its spending.
- Cost rows use an idempotency key, so a retry never charges twice.
- **Circuit breaker.**
  - It opens after 5 consecutive failures and retries after 30 s.
  - While open, the task *pauses at a checkpoint* and resumes later. It never fails.
- **Adding a new provider:**
  - It must pass the shared adapter contract test suite.
  - A second adapter must need zero workflow changes.

**Scope**

- **MVP:** one adapter and two tiers (cheap and strong).
- **Later:** more providers and finer routing.

**Done when.**

- The contract suite passes.
- A search for provider SDK imports outside the adapter package finds nothing.

**Old build.** Built and contract-tested.

### 5.16 Context engineering

**What and why.** Each agent should see the *right* context within budget, and critical facts must survive compression.

**Budget (§H.1)**

```text
window 128,000 × 0.80 fill = 102,400
  − system prompt 2,000 − output 4,000 − recent conversation 8,000 − architecture summary 2,000
  = 86,400 for retrieved context, split per phase:
requirements    task_context 4,000 · precedents 2,000 · history 1,000
design          repo_map 5,000 · structural_graph 12,000 · design decisions 3,000 · patterns 3,000
implementation  task_spec 3,000 · symbols 8,000 · interfaces 2,000
qa              diff 10,000 · impact_set 5,000 · regression_history 2,000
deployment      config 3,000 · deploy_history 1,000
```

**Prompt layout (tiers)**

| Tier | Holds | Compaction |
|---|---|---|
| T0 | Stable prefix: system prompt, tool schemas, architecture summary, then the task repo map | Never |
| T1 | Context Ledger (pinned facts) | Never |
| T2 | Working window: task spec, recent tool results | Cleared at 40% pressure |
| T3 | Compacted history | Compacted at 70% pressure |
| T4 | Blackboard pointers | Never inlined |

**Injection order inside the agent message**

1. Architecture summary
2. Repo map for the task scope
3. Handoff packet
4. Task-specific retrieved context

**Compression.** Run the cheapest step first:

1. Structural filter.
2. Deduplicate.
3. Replace bodies with signatures.
4. Evict least-recently-used content.
5. Summarize with a fast model.

If it is still too big, split the task.

**Context Ledger**

```text
ContextLedgerEntry
  fact_id, task_id
  kind: decision | constraint | interface | assumption | discovered_fact | unresolved_issue | error | validation_result
  subject (symbol_id / path / module / subtask_id)
  statement (≤ 200 chars); provenance_refs [pointer]
  phase, plan_version?, wave_index?, confidence
  status: active | superseded | resolved; created_at
```

**Rules**

- Ledger entries are derived deterministically from typed state and are never compressed.
- The cap is 200 entries; superseded and resolved entries are evicted first.
- Compact at wave boundaries first.
- Merge into the existing summary instead of regenerating it.
- Every eviction leaves a pointer.
- Use stable JSON: sorted keys and no timestamps in T0, so provider prompt caching works.
- Measure tokens **per task**, not per request.

**Scope**

- **MVP:** the handoff caps, Blackboard pointers, and the injection order.
- **Later:** tiers, the ledger, compression, and the PPR repo map. Add them when you hit limits.

**Done when.** There are at least 40% fewer tokens per task with no drop in success rate.

### 5.17 Observability

**What and why.** You need to see what ran, why, and what it cost, without observability ever affecting behavior.

**What it looks like**

```text
TelemetrySink (never raises; failures are swallowed and counted)
  start_span(name, kind, attributes, parent?) → span
  end_span(span, status: ok | error | cancelled, attributes)
  emit_event(name, attributes, span?)
  record_metric(name, value, attributes)
  span(...)  context-manager form

Span hierarchy: TASK > PHASE > MANAGER > AGENT > LLM_CALL | TOOL_CALL | VALIDATION
                plus TOPOLOGY_SELECTION, WAVE_SCHEDULER, FAN_IN, HITL

AgentEvent (UI/audit projection of spans + committed state changes)
  event_id, task_id, timestamp, agent_id, phase, span_id?, parent_span_id?
  event_type: agent_started | agent_tool_call | agent_tool_result | agent_token_stream
            | agent_completed | agent_failed | masc_flag | hitl_required | hitl_responded
            | phase_completed | task_completed | rollback_initiated | feedback_loop_triggered
            | worker_coordination_packet_emitted | clarification_escalated
            | clarification_resolved | fan_in_replan_triggered | task_cancelled
  payload {..}
```

**Rules**

- Spans must truly nest: the parent context is propagated, not just stored as an attribute.
- Use one tracer setup per process.
- Every event carries its span id.
- No workflow step may read events or spans to decide anything.
- Tracing library imports are allowed in one module only.
- Retention: full traces for 90 days; task outcomes indefinitely.

**Scope**

- **MVP:** the sink, nested spans, and cost per call.
- **Later:** dashboards.

**Done when.** One task's trace shows the full hierarchy, with correct parents and LLM and tool spans.

**Old build.** Built, but spans didn't nest (pitfall P9).

### 5.18 Security, sandbox, and budget governance

**What and why.** Agents run untrusted code and read untrusted text, so contain both.

**Rules (§B.6)**

- **Sandbox.**
  - Every code or command execution runs in an ephemeral container scoped to one task.
  - No network by default; memory and CPU limits; destroyed regardless of outcome.
  - Old defaults: a minimal base image, 256 MB, 0.5 CPU, no network.
- **No raw terminal for the model.** The platform runs lint, type, SAST, and tests in the sandbox, and returns structured results.
- **Least privilege.**
  - Short-lived, task-scoped repo tokens.
  - Tool and integration credentials scoped the same way, including linters, scanners, and integration servers.
- **Prompt-injection defense.** Issue, PR, and comment text and other external content is data, never instructions. A classifier flags imperative patterns before such content enters semantic memory.
- **Secrets redaction.** Credential-shaped strings are stripped before any content enters a model call.
- **No standing production credentials.** Deploys go only through existing CI/CD, behind gates.
- **Supply chain.** Pin tool versions, audit them periodically, and run an untrusted-tool policy.
- **Budget.**
  - Per-task ceilings on tokens, cost, and retries.
  - Cost is tracked per agent and per phase.
  - The budget check fails closed: any error counts as "exceeded".

**Sandbox API**

```text
run_in_sandbox(task_id, command [string], timeout_s, network = false) → SandboxResult
SandboxResult { stdout, stderr, exit_code, duration_ms, timed_out }
```

On timeout, **stop the container first**, then kill the client. Killing only the client leaves an orphan container that auto-remove never sees.

**Scope**

- **MVP:** sandbox, budget, secrets redaction, PR-only changes.
- **Later:** the injection classifier and supply-chain audit.

**Done when.**

- A sandbox escape test passes.
- A budget-exceeded task goes to BLOCKED.
- A secret planted in the repo never appears in a prompt log.

### 5.19 Evaluation

**What and why.** Measure whether the platform is getting better, and catch regressions when prompts, models, or code change.

**What it looks like**

```text
RunRecord        task_id, experiment_id?, agent_version, prompt_version, model_ids,
                 orchestration_version, evaluation_version, spans_ref?, artifact_refs, outcome
Score            metric_id, value, unit, confidence?, evidence [Evidence]
Evidence         kind: metric | artifact_ref | span_id | human_note | judge_rationale; pointer; detail
EvaluationCase   case_id, work_type, repo_fixture, prompt, expected {required_files, acceptance_criteria, ..}, labels
Experiment       experiment_id, name, baseline_experiment_id?, dataset_id, dataset_version,
                 agent_version, prompt_version, model_ids, notes
Evaluator.evaluate(run, case?) → [Score]
```

**Rules**

- Evaluators read RunRecords built by a loader from stored data. They never touch workflow-engine internals, and never read events to score.
- Use deterministic methods by default. An LLM judge is opt-in per metric, must attach a rationale and a confidence, and cannot gate CI until it is calibrated.
- Change **one** version field per experiment, so a change in score can be attributed.

**MVP metrics**

| Metric | How it is computed |
|---|---|
| Task success | — |
| Cost | — |
| Cycle time | — |
| Tokens | — |
| HITL count | — |
| Rollback count | — |
| Retry and validation-fail rate | — |
| Fix rate | correct files ÷ required files |
| Token efficiency | fix rate ÷ (tokens / 1000) |
| Transition legality | — |
| Replan cap honored | — |
| Happy-path call count | — |
| WCP schema completeness | — |

**KPI targets (§L.2)**

| KPI | Target |
|---|---|
| Fix rate | above 0.85 |
| Human interventions per routine task | fewer than 2 |
| Rollbacks | under 10% |
| Failure attribution | above 85% |
| Auto-recovery | above 75% |
| First-try tool-call accuracy | above 90% |
| Hallucination rate | under 5% |

**Scope**

- **MVP:** a RunRecord log plus the deterministic metrics.
- **Later:**
  - a golden dataset
  - experiment-vs-baseline CI
  - shadow-mode graduation
  - LLM judges

**Done when.** Golden-dataset resolution is tracked against a baseline.

### 5.20 API and UI

**What and why.** Humans submit, watch, answer, and approve. Every screen is a read layer over the objects above; the UI adds no new data model.

| # | Screen | Shows | MVP |
|---|---|---|---|
| 1 | New task | Intake form | ✓ (merged into the task list) |
| 2 | Requirement interview | The current question, plus questions auto-answered from the repo with their evidence | ✓ (part of the inbox) |
| 3 | Workflow overview | The profile in plain language, and which rule fired | Later |
| 4 | Phase view | Position in the state machine; loops shown | ✓ (part of task detail) |
| 5 | Active agents | Running agents and their current tool call | Later |
| 6 | Timeline | Phases, loops, approvals, waves, amendments, demotions | Later |
| 7 | Questions queue | Open clarifications | ✓ (inbox) |
| 8 | Approval requests | Evidence bundle, confidence breakdown, decision buttons, timeout countdown | ✓ (inbox) |
| 9 | Agent logs | Trace detail | Later |
| 10 | QA summary | Checks run and results; bug reproduction shown first | Later |
| 11 | Deployment | Strategy, canary charts, thresholds | Later |
| 12 | Final report | Done checklist, cost, HITL history, files, KPIs | Later |

- **MVP is 3 screens:** task list (with submit), approval and question inbox, and task detail (phase, cost, artifacts).
- **Live updates** push AgentEvents to the client.

**Done when.** Every approval and answer goes through the UI.

---

## 6. Repository Intelligence in depth

### 6.1 What it is and why it is a service

Repository Intelligence (RI) is the platform's understanding of the codebase. It answers questions like:

- "where is X defined?"
- "who calls Y?"
- "what breaks if I change Z?"
- "what code is about refunds?"

It is a **long-lived shared service**, not a workflow step:

- It is indexed once and updated incrementally.
- All agents, validators, and the wave planner query it.
- Agents **never** touch its storage directly. Every access goes through the API below, so failures surface in one way.

### 6.2 Layers

| Layer | Contents | Update pattern |
|---|---|---|
| L0 | Raw files in the **working tree**, with uncommitted edits (not git HEAD) | Explicit index/reindex; SHA-256 catalog |
| L1 | Symbols, from a multi-language parser | Incremental, per changed file |
| L2 | Import/call/reference graph | Incremental, changed files only; dependents are a query |
| L3 | Semantic embeddings of code chunks | Incremental, only chunks whose content hash changed |
| L4 | Architecture summary and cached summaries | Invalidated by content hash plus dependency hash |

**Why the working tree:** agents edit files that are not committed yet, and RI must see those edits.

### 6.3 Data model

```text
Symbol         id = "{file_path}::{qualified_name}", kind (module|class|function|method), name,
               file_path, start_line, end_line, signature?, docstring?
SearchHit      file_path, line, snippet, score               (lexical)
CodeChunk      symbol_id?, file_path, kind, chunk_text, content_hash, start_line, end_line,
               chunk_tokens, truncated, score?               (semantic)
ImpactSet      changed_files, affected_files, affected_symbols, depth
ContextBundle  chunks [CodeChunk], total_tokens, truncated   (fused retrieval)
IndexStatus    state: unindexed | fresh | stale, file_count, stale_paths, catalog_hash?
CatalogDiff    created, modified, deleted, unchanged         (by SHA-256 of file bytes)
ReindexStats   created, modified, deleted, unchanged, files_parsed, files_parse_error,
               symbols_indexed, chunks_embedded, chunks_skipped_unchanged,
               lexical_rebuilt, graph_updated, elapsed_s, catalog_hash
IndexStats     ..., per_extension {ext: {parsed_ok, parse_error, skipped}}   unsupported languages are visible
RepoMap        files [{path, score, symbols [{name, signature}]}], token_estimate, seed_ids
```

### 6.4 API

**Indexing**

| Method | Purpose | Status |
|---|---|---|
| `index(rebuild=false)` | First index of this tree; `rebuild=true` wipes it and starts over (one pass) | Built (the rebuild double-processed, pitfall P4) |
| `reindex()` | Hash-diff the whole tree; update only what changed | Built |
| `reindex_paths(paths)` | Scoped update for paths an agent just wrote, including both sides of a move | Built |
| `index_status()` | unindexed, fresh, or stale, plus the stale paths | Built |

**Symbols and structure**

| Method | Purpose | Status |
|---|---|---|
| `get_symbol_signature(symbol_id)` | The signature line; never returns empty | Built |
| `get_symbol_body(symbol_id)` | Exact source from disk, after the freshness check | Built |
| `get_file_structure(path)` | Symbols in a file, ordered by position | Built |

**Graph**

| Method | Purpose | Status |
|---|---|---|
| `get_callers(symbol_id, depth=1)` | Who calls this | Built |
| `get_callees(symbol_id, depth=1)` | What this calls | Built |
| `get_dependencies(path)` | Files this file imports | Built |
| `get_dependents(path)` | Files that import this file | Built |
| `get_impact_set(changed_files, depth?)` | Blast radius. A query; never triggers re-embedding | Built |

**Search**

| Method | Purpose | Status |
|---|---|---|
| `search_codebase(query, top_k=10)` | Exact tokens or regex, for identifiers you already know | Built |
| `search_concepts(query, top_k=5, kinds?, paths?, min_score?)` | Natural-language semantic search, with overlap deduplication | Built |
| `find_similar_implementations(code, top_k=3, ...)` | Semantic search where the query is code | Built |
| `find_relevant_context(task, scope, max_tokens)` | Fused retrieval (RRF) with budget packing | **To build** |

**Overview**

| Method | Purpose | Status |
|---|---|---|
| `get_architecture_summary()` | Deterministic JSON from the parsed syntax tree | Built |
| `get_repo_map(seeds, budget_tokens=2500, agent_phase)` | Personalized PageRank map | **Stub** (raw in-degree) |

**History and knowledge**

| Method | Purpose | Status |
|---|---|---|
| `get_regression_history(symbol_id)` | Past failures and fix patterns for a module | **To build** |
| `get_design_decisions(symbol_id)` | Design records (ADRs) touching a module | **To build** |
| `get_change_frequency(path)` | Churn, from git history | **To build** |

Every read method takes `refresh=false`. When the index is stale, a read raises a stale-index error unless `refresh=true`, in which case it reindexes first.

### 6.5 Indexing pipeline and its optimizations

```text
1  Walk the working tree → eligible files
     language allowlist (old: .py .ts .tsx, not .d.ts), deny list (vendor, generated, build), 1 MiB cap
2  Hash every file (SHA-256) → CatalogDiff vs the stored catalog
3  For each created/modified file: parse ONCE → symbols + graph edges + chunks from the same parse
     parse failure → keep the catalog row marked parse_error (counted, never silently dropped)
4  Deleted files → remove their symbols, edges, chunks
5  Chunks: functions/methods embed the full body; classes embed signature + docstring only;
     max 24 KiB per chunk
6  Embed only chunks whose content_hash changed
7  Commit atomically: write new embeddings, then delete old rows, in one transaction;
     rebuild the lexical index (if any) into a temp location and swap it in BEFORE the catalog commit
8  Dependents are NOT re-indexed — impact is answered at query time
9  After a restart, load the graph lazily on first query (no full rebuild)
```

| Optimization | Why |
|---|---|
| Hash catalog, so only changed files are processed | Target under 10 s for a 20-file change |
| One parse feeds three layers | No repeated parsing |
| Content-hash embedding skip | Embedding cost scales with changes, not repo size |
| Class chunks hold the signature only | Smaller vectors, no duplicated method text |
| Over-fetch neighbors, collapse overlapping spans, never let a class header hide its methods | Semantic success@5 went from 94% to 100% |
| Atomic swap of the lexical index, with a timeout and a network-less build | Search never sees a half-built index |
| Per-extension parse stats | Unsupported languages are visible, not silent |

### 6.6 Freshness

- **States.**
  - `unindexed`: no catalog.
  - `fresh`: the catalog matches the working tree.
  - `stale`: some paths drifted.
- A stale index **blocks every read**. Mixed fresh and stale data is not safe to serve as "current code".
- Workers call `reindex_paths` after every write, so their own edits are immediately visible.
- Later additions: git hooks and a nightly full reindex.

### 6.7 Retrieval strategy: which signal answers which question

Keep the four signals **separate** and measure each on its own. Fuse them only once each is measured.

| Question | Best signal | Method |
|---|---|---|
| "Where is `UserService.delete` defined?" | Symbols | `get_symbol_*`, `get_file_structure` |
| "Find this error string or identifier" | Lexical | `search_codebase` |
| "Who calls this?" / "What breaks?" | Graph | `get_callers`, `get_dependents`, `get_impact_set` |
| "Code about refunds" (wording mismatch, e.g. "delete user" vs `deactivate_account`) | Semantic | `search_concepts` |
| "What matters around these files?" | Graph ranking | `get_repo_map` |
| "Give me the best context within N tokens" | Fusion | `find_relevant_context` |

**Large-repo strategy (§H.7)**

1. **Grep first.**
   - It is always fresh and precise on exact identifiers.
   - Use **windowed reads of 50–100 lines**, never whole files.
2. **Personalized repo map per task** (6.8).
3. **Semantic search, fused with RRF,** for wording-mismatch cases.
4. **Hierarchical localisation before coding.** This is context assembly, not scheduling.
   1. Grep and glob find candidate files.
   2. Skeletons (signatures only) of those candidates are built.
   3. Precise locations are picked from the skeletons.
   4. The worker receives skeletons of the candidates plus full bodies **only** for the precise locations. Full-file injection was measured to *hurt* localisation accuracy.
5. **Never load the full graph into a prompt.** Use point lookups only.

**Fusion (RRF)**

```text
fused_score(item) = Σ over signals s of 1 / (k + rank_s(item))      k ≈ 60 is the common default
```

RRF is robust to the different score scales across signals. Pack results by fused score until the token budget is reached, then set `truncated`.

### 6.8 Repo map with personalized PageRank

A *global* "most important files" map is useless on 100k files. Instead, PageRank's random restarts jump back to **task seed files**, so probability concentrates on code near what the task is about.

**Seeds.** They are collected once per agent call, then deduplicated and capped at **12**:

| Seed source | Weight |
|---|---|
| S1: explicit paths, from the ticket, handoff packet, WCP, or escalation answers | 1.0 |
| S3: files already touched in this run, plus ledger interface and discovered-fact entries | 0.8 |
| S4: impact and localisation hints | 0.6 |
| S2: grep hits for identifiers in the goal text (cap about 8; prefer source files over tests) | 0.5 |
| S5: fallback, the entry points from the architecture summary (low confidence) | 0.2 |

**Ranking and rendering**

```text
graph   = import/call/reference graph for the scope containing the seeds (never the full federated graph)
v       = seed weights, L1-normalized (non-seeds = 0)
score   = PPR(graph, v, damping 0.85)
ranked  = sort files by score; exclude generated/vendor/lockfiles; demote tests unless QA phase
pack    = top files until the budget (default 2,500; design 5,000; workers 1,500–2,500; QA 2,000)
          if a file's symbol list is huge, keep its most-referenced or exported symbols
cache   = keyed by (graph_version, seeds, damping)
```

```text
# Repo map (personalized PageRank | seeds: auth/service.py, api/routes/user.py)
auth/service.py                          score=0.142
  class AuthService
  def authenticate(user_id: str, token: str) -> Session
  def revoke_session(session_id: str) -> None
api/routes/user.py                       score=0.091
  def delete_user(user_id: str) -> None
db/models/user.py                        score=0.067
  class User(Base)
```

- The map holds signatures only, never bodies.
- Agents use it as an orientation index, then expand with symbol, caller, and grep tools.
- Each worker gets a map seeded on *its own* target files.
- Refresh it at most once per wave.

### 6.9 Architecture summary

The summary is generated from the parsed syntax tree, **never by an LLM**. It is rebuilt when the graph structure changes, and injected into every agent prompt.

```json
{
  "services": ["auth", "payments", "notifications"],
  "service_map": {
    "auth": {
      "entry_points": ["POST /login", "POST /refresh"],
      "key_symbols": ["UserService", "TokenManager"],
      "dependencies": ["db.users", "cache.sessions"],
      "tech_stack": ["<detected from manifests>"]
    }
  },
  "shared_modules": ["utils.logging", "utils.validation"],
  "database_entities": ["User", "Session", "AuditLog"],
  "api_boundaries": ["REST /api/v1", "RPC auth.proto"],
  "cross_shard_deps": [{"from": "payments", "to": "auth", "via": "auth.TokenManager"}]
}
```

### 6.10 Useful RI capabilities to add

These go beyond what was built. Each one feeds a specific feature.

| Capability | What it gives | Feeds | How to derive it |
|---|---|---|---|
| **Test-to-code map** | Which tests exercise which symbols and files | Test-impact analysis (5.12), the test_coupling edge (5.8) | Record coverage per test once, plus test imports from the graph |
| **Shared-resource detector** | Marks migrations, schema files, ORM models, API specs (OpenAPI, proto, GraphQL), config, lockfiles | `shared_resource` edges, TP-06, the `has_database_changes` and `has_api_contract_changes` flags | Path patterns plus parser queries |
| **Entry-point and route extraction** | HTTP routes, CLI commands, jobs, event handlers | The architecture summary, Spec QA, API contract checks | Framework-agnostic parser queries for decorators and registrations |
| **Git-history signals** | Change frequency (churn), co-change coupling, last authors | `get_change_frequency`, risk scoring, hidden dependencies, reviewer suggestions | `git log` mining, cached per catalog hash |
| **Ownership map** | Owners per path | Approval routing, shard boundaries | Parse CODEOWNERS plus git history |
| **Regression history** | `{module, failure_type, fix_pattern}` from past tasks | `get_regression_history`, QA focus, the precedent signal | Written by QA (5.12) |
| **Design-decision index** | Design records (ADRs) linked to modules | `get_design_decisions`, the Design Manager | Written when a design is approved |
| **Precise reference resolution** | Resolves attribute and method calls, such as `self.pool.acquire()` | Better callers/callees and impact sets (fixes benchmark miss g06) | Type-aware analysis or language-server indexes (7.3) |
| **Rename detection** | A same-hash delete plus create counts as a move | Keeps history and ownership across renames | Catalog hash matching |
| **Untrusted-content tagging** | Marks text from issues, PRs, and comments | Prompt-injection defense (5.18) | Tag at ingestion |
| **Secret-aware retrieval** | Redacts secrets in returned snippets | Secrets redaction (5.18) | Run the secrets scanner's patterns on results |
| **Query cache** | Reuses results within the same catalog hash | Lower RI cost per task | Key on `(method, args, catalog_hash)` |
| **Sharding (at scale)** | Domain shards, plus an index of indices for cross-shard edges | Repos with 1M+ files | Shard boundaries from the dependency graph, not from directories |

### 6.11 Query budgets per consumer

| Consumer | Budget |
|---|---|
| Wave planner (per plan) | ≤ 50 RI calls; unchecked pairs become unverified blocking edges (D15) |
| Requirements session | 16 RI calls; semantic top-k 3; lexical top-k 10 |
| Requirements evidence plan (per slot) | `max_ri_calls`, e.g. 4 |
| Repo Architecture Analyst | Structural queries, 2 hops from the affected modules |
| Worker | Bounded by the 25-tool-turn limit (section 12) |

### 6.12 Failure contracts (fail closed)

| Failure | Caller | Behavior |
|---|---|---|
| RI times out or is unavailable | Worker | `ClarificationEscalation(ri_consulted=true)` with empty evidence; the worker stops |
| RI times out or is unavailable | Fan-in cross-check | Treat as a conflict: demote if 2+ branches, else replan |
| RI times out or is unavailable | Confidence scorer or MASC | Confidence is below the floor: block and escalate |
| RI unavailable | Wave planner | TP-01: width 1 |
| A required query returns empty | Worker | Escalate; never guess |
| Malformed response | Any | Escalate; log `ValidationFlag(source=static_tool, flag_type=tool_error)` |
| Stale index | Any read | Stale-index error unless `refresh=true` |
| Symbol not found | Symbol reads | A not-found error; never an empty string |

### 6.13 Benchmark (how RI quality is measured)

- **Corpus.** A small, fixed fixture: 14 files across 5 services, with **29 labeled queries**.
- **Metric: success@5.** Did any of the top 5 results contain a correct answer?
  - Don't use precision@5 when most queries have one right answer: it tops out at 0.20.
- **Score each signal on its own** before fusing, so a miss points to one signal.
- **Freeze the labels and keep the hard queries.** Never edit a label to make a run pass. The benchmark is what found the class-chunk deduplication bug.
- **Old baseline:** 96.2% success@5 overall; semantic 100% after the deduplication fix.
- **Gates:**
  - at least 90% success@5
  - incremental update under 10 s for 20 files
  - at scale, within 5 points of the baseline at 1M files

---

## 7. Tools: build it yourself or use a third-party option

Product names below are **options to evaluate, not recommendations**. Pick per your language mix and constraints, then verify current versions and licenses.

### 7.1 Tool principles

- **The model requests; the platform executes.**
  - Every tool is a platform function with a JSON schema.
  - The platform validates the arguments, runs the tool, and returns a structured result.
- **Least privilege per role.** Each agent gets only the tools in its column of the access matrix (7.4).
- **No raw shell and no network for agents.** Commands are fixed, platform-defined actions such as `run_checks` and `run_tests`.
- **Writes are confined** to the worker's own worktree. Every write triggers `reindex_paths`.
- **Bounded outputs.**
  - Every result has a size cap and a `truncated` flag.
  - Large outputs (logs, diffs) go to the Blackboard and come back as a pointer.
- **Errors are typed:** `{error: not_found | ambiguous | invalid_args | timeout | unavailable | denied, detail}`. An error never comes back as an empty success.
- **Idempotent side effects.** Tool calls that change external state carry an idempotency key.
- **Every tool call is a span**, with arguments (redacted), duration, status, and result size.

### 7.2 Agent-facing tools (the model can call these)

**Reading and navigation**

| Tool | Signature → result | Given to | Build or buy |
|---|---|---|---|
| `read_file` | `(path, start_line, end_line)`, max 100–200 lines → numbered lines, `total_lines`, `truncated` | All code-reading agents | **Build** (trivial). Windowed reads only |
| `list_files` | `(glob, limit=200)` → paths | Code agents | **Build** on a file-walker: `fd`, ripgrep's file listing, or the language's glob |
| `grep` | `(pattern, regex=false, paths?, max_hits=50, context_lines=2)` → hits `{path, line, snippet}` | Code agents, Requirements Analyst, validators | **Build a wrapper.** Engines: ripgrep, `git grep`, or an indexed trigram search such as Zoekt, livegrep, or Sourcegraph |
| `get_file_outline` | `(path)` → symbols with lines and signatures | Code agents | **RI** (`get_file_structure`) |
| `get_symbol` | `(symbol_id, part: signature \| body)` → text | Code agents | **RI** |
| `find_callers` / `find_callees` | `(symbol_id, depth=1)` → symbols | Code agents, Integration Validator | **RI** |
| `get_dependents` / `get_impact_set` | `(paths)` → files and symbols | QA, wave planner, Review | **RI** |
| `search_concepts` | `(query, top_k=5, paths?)` → chunks | Design, Requirements, workers (sparingly) | **RI** |
| `get_repo_map` | `(seeds, budget_tokens)` → rendered map | Usually injected by the context builder, not called | **RI** |
| `read_artifact` | `(pointer)` → content | All | **Build** on the Blackboard |

**Editing (CodeGen workers only)**

| Tool | Signature → result | Build or buy |
|---|---|---|
| `edit_file` | `(path, old_text, new_text, expected_count=1)` → ok, or `not_found` / `ambiguous` | **Build.** The exact search-and-replace format is the most robust for LLMs. References: the search/replace edit formats in open-source coding agents, and the "text editor" or `str_replace` tools that model vendors document |
| `apply_patch` | `(unified_diff)` → ok or conflict details | **Build** on `git apply --check` then `git apply`. Diffs are compact but models get line numbers wrong more often; offer it as an alternative, not the only edit path |
| `create_file` | `(path, content)` → ok; fails if the file exists | **Build** |
| `delete_file` / `move_file` | `(path)` / `(from, to)` → ok | **Build** on git (`git rm`, `git mv`) so history is kept |

**Checking (the platform runs these in the sandbox)**

| Tool | Signature → result | Build or buy |
|---|---|---|
| `run_checks` | `(kinds: [lint, type, sast, secrets], scope: changed \| paths)` → findings `{tool, rule, severity, path, line, message}` | **Build a runner**; buy the analyzers (7.3) |
| `run_tests` | `(selection: impacted \| explicit [ids], timeout_s)` → per-test pass/fail/skip, with a pointer to the logs | **Build a runner** on the language's native test runner plus the test-to-code map |

**Optional**

| Tool | Signature → result | Build or buy |
|---|---|---|
| `lookup_docs` | `(library, topic)` → snippets | Optional and network-gated. Options: a local mirror of library docs, or hosted documentation-lookup servers |

**Not tools, by design**

- **Escalating** is the structured *final output* (`ClarificationEscalation`), not a tool. Workers have no "ask human" tool; only the Requirements Analyst raises clarifications, through HITL.
- **Spawning agents** does not exist as a tool for any agent.

### 7.3 Platform tools (not exposed to the model)

**Execution and code search**

| Need | Build or buy | Options |
|---|---|---|
| Sandbox runtime | Buy the runtime, build a thin wrapper | Containers with no network plus resource limits (Docker, Podman); user-space kernels for stronger isolation (gVisor); microVMs (Firecracker); hosted code sandboxes |
| Worktree and merge manager | **Build** on git | `git worktree`, `git merge --no-ff`, `git merge-tree` for dry-run conflict checks; libgit2 bindings |
| Multi-language parser (L1) | Buy | Tree-sitter grammars; language servers (document symbols); Universal Ctags (lighter, less precise) |
| Precise cross-references | Buy, later | SCIP or LSIF indexers per language (an export format, not a search engine); stack-graphs; language servers (find references) |
| Lexical search | Buy | ripgrep (no index, always fresh, fine to ~100k files); Zoekt or livegrep (trigram index, scales further, needs a rebuild and swap) |
| Embeddings | Buy, through the model adapter | The provider's embedding endpoint (verify it exists and its dimension); a self-hosted open code-embedding model |

**Static analysis and scanners**

| Need | Build or buy | Options |
|---|---|---|
| Lint and format | Buy | Python: Ruff, Flake8. TS/JS: ESLint, Biome. Go: golangci-lint. Java: Checkstyle, SpotBugs |
| Type checking | Buy | Python: mypy, Pyright. TS: `tsc`. Built in for compiled languages |
| SAST | Buy | Semgrep (fast, pattern rules); CodeQL (deep dataflow, slower, periodic); Bandit (Python only) |
| Secrets scanning | Buy | Gitleaks, detect-secrets, TruffleHog |
| Dependency vulnerabilities | Buy | OSV-Scanner, pip-audit, npm audit, Trivy, Grype |
| License and supply chain | Buy, later | Trivy, ScanCode, OSV-Scanner; SBOM generators (Syft) |

**Testing**

| Need | Build or buy | Options |
|---|---|---|
| Test runner | Buy | pytest, Jest, Vitest, `go test`, JUnit |
| Coverage, for the test-to-code map | Buy | coverage.py, Istanbul/c8, JaCoCo, `go test -cover` |
| Test-impact selection | **Build** on RI | Impact set plus the test-to-code map; per-language plugins exist but are optional |
| Mutation testing | Buy, later | mutmut, Cosmic Ray (Python); Stryker (JS/TS, .NET); PIT (Java) |
| Property-based testing | Buy, later | Hypothesis (Python); fast-check (JS/TS) |
| Performance | Buy, later | k6, Locust, Gatling |
| UI automation and accessibility | Buy, later | Playwright, Cypress; axe-core |
| API contract fuzzing | Buy, later | Schemathesis, Dredd, RESTler |
| DAST | Buy, later | OWASP ZAP, Nuclei |

**Safety, integrations, and utilities**

| Need | Build or buy | Options |
|---|---|---|
| Prompt-injection screening | **Build** a simple version first | Regex and heuristic imperative-pattern rules, then optionally a small open classifier model |
| Secrets redaction before prompts | **Build** | Reuse the secrets scanner's patterns on outgoing prompt text |
| Token counting | Buy, or approximate | The provider's tokenizer, or a chars ÷ 4 approximation (the old build), with a safety margin |
| Git host | Buy the API, build the adapter | The GitHub, GitLab, or Bitbucket REST APIs, directly or through tool-protocol servers (e.g. MCP) where available |
| Tickets | Buy the API, build the adapter, later | Jira, Linear, GitHub Issues APIs |
| Notifications | Buy the API, build the adapter, later | Slack or Teams webhooks, email |
| CI/CD trigger | Buy the API, build the adapter | The team's existing pipeline API (GitHub Actions, GitLab CI, Jenkins, and so on) |
| Diff and patch utilities | Buy | `git diff`, `git apply`; language diff libraries |
| Graph ranking (PPR) | Build or buy | Any graph library with personalized PageRank, or about 30 lines of power iteration over an adjacency list |

### 7.4 Tool access matrix

| Tool | Req. Analyst | Design agents | Impl. Manager | Worker | Integration Validator | QA agents | Review |
|---|---|---|---|---|---|---|---|
| read_file, list_files, grep | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| Symbol and graph tools | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| search_concepts | ✓ | ✓ | — | ✓ | — | ✓ | ✓ |
| Edit tools | — | — | — | ✓ (own worktree; includes the regression test writer) | — | — | — |
| run_checks | — | — | — | ✓ | ✓ | ✓ | ✓ |
| run_tests | — | — | — | ✓ (scoped) | ✓ | ✓ | — |
| read_artifact | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

The Implementation Manager gets **no tools** on its decompose call. RI facts reach the plan through the deterministic planner instead.

---

## 8. Scope cuts: cut, simplify, keep

The rule of thumb for a solo rebuild: if a feature needs data you don't have yet (memory, calibration, graduation) or scale you don't have (shards, 8 parallel workers), postpone it.

### 8.1 Cut for now (overkill)

| Item | Why | Use instead |
|---|---|---|
| RI at scale: shards, index of indices, shard coordinator | You aren't indexing 1M files | A single index |
| A prebuilt lexical index | Needs a file mirror, index builds, and atomic swaps | A plain grep engine over files |
| MASC semantic drift check | The schema check and validators catch most bad output | Schema check plus validators |
| Intent Tracker (FL-11) | An extra LLM watching other LLMs | The approval gates |
| Procedural memory, nested delegation | Research items with no data behind them | Nothing yet |
| Design debate | Optional in the blueprint | The reflection pass |
| The 12-screen UI | Too much to build and maintain alone | 3 screens |
| Shadow-mode graduation, experiment CI, delivery metrics | Need many real tasks first | A RunRecord log |
| Mutation, performance, deep dataflow, UI automation, accessibility, contract fuzzing | Heavy tooling, little early value | Lint, type, tests, SAST, secrets |
| Ticket and chat integrations | Not needed to ship | The git host only |

### 8.2 Simplify (keep the idea, shrink it)

| Item | Full version | Start with |
|---|---|---|
| Topology rules | TP-01..TP-08, hard gates and soft caps | Parallel only when files are disjoint; max 2; otherwise sequential |
| Wave demotion | S1–S7 state machine | On conflict, rerun the conflicting subtasks one by one |
| Feedback loops | FL-01..FL-11 | 5 loops |
| Confidence | 4 weighted signals | Validator agreement plus static cleanliness |
| Context engineering | Tiers, PPR map, ledger, compression | Handoff caps plus pointers |
| Model routing | Capability scores per operation | Two tiers: cheap and strong |
| Approval gates | 6 | 3: scope, design, PR/merge, with release folded into PR (D6); deployment is added with the release phase |
| Question bank | 24 slots | About 10 |
| ReplanContext | 15 fields | Previous decomposition, findings, open clarifications |

### 8.3 Keep (this is the core)

- Human approval before anything irreversible, and fail closed when unsure.
- Durable checkpoints plus pause/resume for humans.
- The model adapter layer.
- The sandbox for running code and checks.
- A git worktree per worker, plus a validator before merge.
- Workers never talk to each other; everything flows through the Manager, Fan-in, and stored state.
- The budget kill switch and cost tracking.
- Basic RI: symbols, callers, impact set, semantic search, freshness.
- Contract tests, fakes, and the retrieval benchmark.

---

## 9. Lessons learned

- **GLM needs no custom SDK** because it is OpenAI-compatible.
  - Its embeddings route was unverified, and the provider's pricing page listed no embeddings product.
  - Test embeddings, including the vector dimension, before relying on them.
- **Index the working tree,** because agents edit files that are not committed yet.
- **Evidence first beats a checklist interview.** Answer what the repo can answer, and ask humans only the rest.
- **Use success@5, not precision@5,** when most queries have one correct answer.
- **Score each retrieval signal on its own before fusing.**
- **Freeze benchmark labels.** The hard queries are what find real bugs.
- **Resume can re-run the paused step from the top.** Anything before the pause must be idempotent.
- **Don't mix async cost tracking with sync calls.** Refuse sync calls while a tracker is attached.
- **Declare each constant once,** for example the embedding dimension, which must match the storage schema.
- **Crash tests need deterministic hooks:** a ready/go handshake, then a hard kill. Require 20 of 20 passes.
- **Assert on structure, never on LLM wording.**
- **Grep-checkable boundaries are cheap and catch drift.** Use import-boundary tests for provider SDKs, tracing, and package layering.
- **Work in small atomic tasks** of 1–4 hours: plan, implement, run, test, verify, demonstrate, commit.
- **Requirements the agent framework must meet.** Earlier framework reviews failed options on these points:
  - The LLM must not decide when to spawn sub-agents.
  - The framework must not write its own hidden files or memory.
  - It must work with any OpenAI-compatible provider, not just one vendor's API.
  - It must have durable, inspectable checkpoints that don't depend on unsafe serialization.
  - It must not require a separate opaque runtime.
- **Options rejected earlier, as principles:**
  - Durable-execution engines without native pause-for-human.
  - A learned or ML model router (violates Principle 5).
  - Embedded-only graph stores, for a shared multi-reader service.
  - Heavy cluster orchestration and multi-tenancy at MVP.

---

## 10. Pitfalls from the old build

These are real defects found in the old code or blueprint. They are described generically so they apply to any stack.

### 10.1 Code defects

| # | Problem | Do this instead |
|---|---|---|
| P1 | The step-visit kill switch counted *cost rows*, not step visits | Count each real step entry explicitly |
| P2 | The approval-timeout job was registered but never scheduled, so timeouts never fired | Schedule it, and test that it runs |
| P3 | CI never ran the integration tests | Run the integration tests, against real services, in CI |
| P4 | A full rebuild parsed and embedded everything twice | One pass |
| P5 | Task save/load silently dropped 5 fields (repo refs, lineage, artifact refs, approvals, max retries) | Store every field; add a round-trip test |
| P6 | Knock-on from P5: hotfix routing and the rollback guard read the dropped fields after a reload | Fixed by P5 |
| P7 | Confidence was never computed, so "low confidence" rules would always fire | Compute it, or store explicit null and handle null first |
| P8 | The drift check was a stub that always returned "not checked" | Build it, or remove it; never ship a silent stub |
| P9 | Traces didn't nest: the parent was only an attribute, there were several tracer setups, and events had no span id | Propagate real context; one tracer setup per process |
| P10 | The requirements engine was never called by the workflow | Wire every built library in, behind an end-to-end test |
| P11 | Answers seeded from the request were labeled "human" | Use `source="request"` |
| P12 | An event kind was defined but never emitted | Emit it or delete it |
| P13 | The question queue silently dropped questions in a cycle when built without the loader | Raise a cycle error everywhere |
| P14 | The same constant was declared in two places | One definition |
| P15 | The agent base was single-turn and read only the first tool call | A proper tool loop that handles *every* tool call (5.8.4) |
| P16 | On timeout, killing the container client left an orphan container | Stop the container first, then kill the client |

### 10.2 Blueprint defects

| # | Problem | Fix |
|---|---|---|
| P17 | Rule 3 compared confidence to the floor *before* checking for null (a crash), and the context defaulted confidence to 0.0 (a guess) | Nullable; check null first |
| P18 | Model-tier escalation called a router inside a function that returns a tier, and early returns meant the Feedback Agent route fired only at the top tier | Return `{tier, route}` |
| P19 | Rules 2, 3, and 5 *appended* approvals to a list that already had all of them (no effect, duplicates). Rule 1 *replaced* the list and dropped `pr` | Each rule sets its full approval list explicitly; critical keeps `pr` |

---

## 11. Resolved decisions (former contradictions)

Every conflict found in the old blueprint, docs, and code is decided here. The specs above are already updated to match.

**If code or another doc disagrees with this table, this table wins.**

### 11.1 Workflow, approvals, and loops

| # | Topic | Conflict | Decision | Applied in |
|---|---|---|---|---|
| D3 | Decision name | The blueprint typo `request_changesSun` | `request_changes` | 5.4 |
| D4 | Security approval | Rule 1 requires it, but the old roster had no security gate | `ApprovalGate(security)` exists and pauses in the design phase. It fires through Rule 1 | 5.4, 5.10 |
| D5 | QA depth for hotfixes | Rule 2 used a value outside the `qa_depth` enum | `qa_depth = standard`. Agent selection adds the Bug Validation Agent | 5.10 |
| D6 | When approvals fire | "Risk ≥ medium" in the roster vs always in the conservative profile; and 3 MVP gates vs 5 in the profile | Until the policy engine exists, the conservative profile applies: all gates whose phase is built. At MVP the release gate is folded into the PR gate, so 3 gates fire. Later, "risk ≥ medium" is Rule 5 | 1.5, 5.4, 5.10, 8.2 |
| D7 | Bug Validation placement | It must run before any fix, but was placed inside QA | Bug reproduction is the last step of requirements, after the scope gate. QA re-runs the reproduction after the fix | 1.4, 4.2, 5.5a, 5.12 |
| D8 | Feedback Agent trigger | "After the 2nd rejection" vs "at max retries (3)" | 2 rejections means a model-tier upgrade. 3 rejections means the Feedback Agent. A failed revision goes to a human. The counter resets after Feedback Agent instructions | 5.2, 5.10 |
| D9 | FL-06 triggers | Spec QA only vs any critical QA or test failure | All three trigger it (Spec QA fail, a real test failure, a critical non-security finding), with one shared cap of 3. Critical security findings use FL-08 | 5.11 |
| D10 | FL-09 owner | "Health Monitor" vs "Monitoring Manager" | Monitoring Manager. After the automated rollback, the task goes to BLOCKED | 4.2, 5.1, 5.11 |
| D11 | Agent roster | Agents named in agent selection were missing from the roster | All of them are added, with kind and tools, as conditional agents | 4.2, 5.10 |
| D14 | Requirements exit | The blueprint exits on confidence ≥ 0.80; the built engine exits on the deterministic sufficiency gate | The sufficiency gate decides the exit. Confidence is computed afterwards. If it is below 0.80, the scope gate shows a flag and the human decides | 5.6, 5.7 |

### 11.2 Data model, planning, and process

| # | Topic | Conflict | Decision | Applied in |
|---|---|---|---|---|
| D1 | Subtask idempotency key | 3 parts vs 4 parts | 4 parts: `(task_id, subtask_id, plan_version, attempt_number)` | 5.2, 5.8 |
| D15 | Unchecked dependency pairs | "Advisory" (non-blocking) vs "treated as if they exist" | A **blocking** edge with evidence "unverified: RI budget" and confidence 0, counted in `unverified_edge_count` | 5.8.3, 6.11 |
| D16 | Task states | Cancellation existed but the state enum had no `cancelled`; "blocked" was called terminal | `cancelled` is added. `blocked` is a holding state with `blocked_from` | 1.4, 2, 5.1, 5.2 |
| D17 | Retry vs escalation | One retry loop mixed transient errors with validator rejections | Two separate levels: transient retry in place, and the rejection escalation ladder | 5.2, 5.10 |
| D18 | Who writes regression tests | QA "commits tests", but QA agents have no edit tools | A CodeGen worker run (the regression test writer) dispatched by the QA Manager | 4.2, 5.12, 7.4 |
| D19 | Step-visit ceiling | A fixed 100 vs `waves × (retries + 1) × 3`, which can exceed 100 | `max(100, waves × (retries + 1) × 3 + 30)`, recomputed on each new plan | 5.2 |
| D20 | Policy rule coverage | Rules 1–5 left low-risk tasks that weren't auto-merge eligible landing on the medium-risk default | Rule 6 is added for them: pr and deployment approvals; minimal QA | 5.10 |

### 11.3 Naming, metrics, and the UI

| # | Topic | Conflict | Decision | Applied in |
|---|---|---|---|---|
| D2 | Number of UI screens | 11 vs 12 | 12 in the full spec; 3 at MVP | 5.20 |
| D12 | Retrieval metric | precision@5 vs success@5 | success@5 everywhere | 6.13 |
| D13 | Run id | Truncate to 255 vs raise | Raise on ids over 255; never truncate | 5.1 |

---

## 12. Decided numbers (former gaps)

These are starting values. Changing one is a config change, made with a test, never a code edit scattered across files.

### 12.1 Thresholds and gates

| Number | Value | Notes |
|---|---|---|
| Rule 3 confidence floor | **0.80** | The requirements floor. The profile is resolved at requirements exit |
| Auto-merge ceiling (Rule 4) | **0.95** | Rule 4 stays switched off until low-risk shadow-mode graduation passes |
| Shadow-mode graduation, per risk tier | **≥ 50 cases, ≥ 95% agreement with the human decision, zero critical misses** | Measured on golden and shadow runs |
| CI regression epsilon | **2 × the standard deviation over 5 baseline runs**, at least 1 percentage point for rates | Per metric |
| Canary thresholds (FL-09) | **under 5%** delta auto-promote · **5–15%** human review · **over 15%** roll back | Error rate, p99 latency, saturation |
| Shard boundary ratio | **Cross-shard edges ≤ 10% of within-shard edges** | Only once sharding is built |

### 12.2 Runtime limits

| Number | Value | Notes |
|---|---|---|
| Circuit breaker | **5** consecutive failures, retry after **30 s** | The old code values |
| Step-visit ceiling | **max(100, waves × (retries + 1) × 3 + 30)** | Counts real step entries |
| HITL timeout | **60 min**, then escalate | Never auto-approves |
| Max plan amendments per attempt | **3** | Then a Manager replan |
| Worker tool turns | **25** | On reaching the limit, the worker stops with an escalation |
| Tokens per tool result | **4,000** | The rest is offloaded to the Blackboard |
| Worker wall time | **15 min** | Tune from sandbox measurements |

### 12.3 Context and retrieval

| Number | Value | Notes |
|---|---|---|
| T2 working window | **The last 10 tool results, capped at 8,000 tokens** | Matches the "recent conversation" budget |
| RRF constant k | **60** | Tune on the benchmark |

---

## 13. Open tech-stack decisions

These choices are **deliberately left open**. For each, the table lists what the platform requires. Evaluate options against these requirements, not against what the old build used.

**Workflow and storage**

| Decision | Hard requirements | Nice to have |
|---|---|---|
| Implementation language(s) | Strong typing or runtime schema validation; a good async story; parsers and analyzers for the target languages | The same language as most target repos |
| Durable workflow runner | Checkpoint after every step; pause for a human and resume with input, across restarts; dynamic fan-out from *data* without changing the workflow definition; idempotent replay; inspectable state; no LLM-driven control flow | Local dev without heavy infrastructure; time-travel debugging |
| Durable store | Transactions; JSON fields; idempotent inserts (unique keys); migrations with drift checks | One store for state, logs, and costs at MVP |
| Vector index | Metadata filters (path, kind); atomic update with the catalog; dimension declared once | Lives in the same store at MVP |
| Graph store | Point lookups (callers, dependents, impact); incremental edge updates; PPR or exportable adjacency | In-memory at MVP, with persistence and lazy reload |

**Execution and infrastructure**

| Decision | Hard requirements | Nice to have |
|---|---|---|
| Job queue and scheduler | Scheduled jobs (HITL timeouts); worker leases; at-least-once delivery with idempotent handlers | Priority partitions by risk tier |
| Sandbox | No network by default; CPU and memory limits; guaranteed teardown; per-task isolation | Snapshot or fast start |
| Agent framework | **Optional.** If used, it must meet the requirements in section 9; otherwise use the adapter plus a small tool loop | — |

**Interface and observability**

| Decision | Hard requirements | Nice to have |
|---|---|---|
| API and live updates | Request/response plus server push of events; auth with roles | — |
| UI | Task list, inbox, task detail | — |
| Tracing backend | Nested spans; export to a standard format; never blocks the workflow | LLM-call-aware views |

**Decision checklist for each choice**

- Can it be swapped behind an interface?
- Does it work in local dev with one command?
- Does it fail closed?
- Can it be tested with a fake in unit tests and the real thing in integration tests?

---

## 14. Done criteria and build order

### 14.1 Done criteria

| Capability | Proven when |
|---|---|
| Foundations | A dummy task goes intake → sandbox → trace → budget-tracked completion, with a full audit trail |
| Durable execution | A paused task survives a hard kill and resumes correctly in 20 of 20 trials |
| Model layer | No provider SDK use outside the adapter package; the contract suite passes |
| Repository Intelligence | ≥ 90% success@5; incremental update under 10 s for 20 files |
| Requirements | Asks on ≥ 95% of ambiguous inputs; skips on ≥ 95% of well-specified ones |
| Intake | A confidence score, or an explicit null, is logged on every intake |
| Design and implementation | ≥ 80% first-pass static-check success for low and medium risk |
| QA | Catches ≥ 95% of seeded defects |
| Governance | Zero agent commits on a protected branch without approval |
| UI | Every approval goes through the UI |
| Policy engine | ≥ 90% agreement with an architect; the full combination matrix is tested |
| RI at scale | success@5 within 5 points of the baseline at 1M files |
| Context engineering | ≥ 40% fewer tokens per task at the same success rate |
| Advanced QA | ≥ 95% on a seeded-vulnerability benchmark |
| Integrations | A ticket becomes a human-approved PR with no manual re-entry |
| Evaluation | Golden-dataset resolution is tracked against a baseline |
| Hardening | Every production risk has a passing chaos test |

### 14.2 Test setup to rebuild

- **A model adapter contract suite.** Every provider must pass it.
- **Fakes:**
  - a fake model adapter
  - a fake RI
  - a deterministic hashing embedder
  - tests run with no network and no API key
- **Factories** for tasks and chunks.
- **Real services in integration tests,** using ephemeral containers.
- **A fixture repo,** small and known, for indexing tests.
- **The retrieval benchmark:** 14 files, 5 services, 29 labeled queries.
- **Boundary tests:**
  - provider SDKs only in the adapter package
  - tracing only in one module
  - workflow code never imports evaluation, and the reverse
- **A crash-recovery test,** with ready/go hooks, a hard kill, and 20/20 passes, nightly and on main.
- **A schema-drift check** between models and migrations, in CI.

### 14.3 Build order

1. **Contracts and the test setup.** The Task, working state, channel schemas and caps, boundary tests, and fakes.
2. **Model layer.** The adapter, the contract suite, pricing, and the circuit breaker.
3. **Repository Intelligence.** The catalog, symbols, graph, semantic search, freshness, and the benchmark as a gate.
4. **Durable workflow.** Checkpoints, pause/resume, the kill switch, the HITL log plus a *scheduled* timeout job, and the crash test.
5. **Requirements engine,** wired in as the requirements phase.
6. **Approval gates, validators, and the schema check.**
7. **Implementation.**
   1. The tool loop and the agent tools.
   2. The simplified wave planner.
   3. Worktrees.
   4. Fan-in.
   5. The Blackboard.
   6. The Integration Validator.
8. **QA (MVP set), then the PR flow.**
9. **The 3-screen UI.**
10. **The policy engine,** then context engineering, advanced QA, integrations, evaluation, and hardening.

---

## 15. Appendix: old repo map (reference only)

Use these paths to read the old *logic*. The old code's framework and database choices are not recommendations. Paths are relative to `sdlc-platform/`.

**Domain logic**

| Topic | Old location |
|---|---|
| Repository Intelligence API and models | `packages/repo_intel/api.py`, `packages/repo_intel/models.py` |
| Indexing (catalog, incremental, chunks) | `packages/repo_intel/indexers/`, `packages/repo_intel/vector/chunks.py` |
| Architecture summary | `packages/repo_intel/` (summary builder) |
| Retrieval benchmark | `tests/benchmark/` |
| Requirements engine | `packages/requirements_engine/` (claims, extract, snapshot, predicates, seed, rank, sufficiency, engine) |
| Question bank | `configs/question_bank/*.yaml` |
| Model adapter, router, circuit breaker | `packages/model_adapters/` |
| Pricing registry | `configs/pricing/registry.yaml` |

**Platform plumbing**

| Topic | Old location |
|---|---|
| Sandbox | `packages/common/sandbox.py` |
| Budget and confidence | `packages/common/budget.py`, `packages/common/confidence.py` |
| HITL store, approval gate, validator templates | `packages/orchestration/hitl_store.py`, `packages/agents/templates/` |
| Crash-recovery test | `tests/chaos/` |
| Adapter contract suite and fakes | `tests/contract/`, `tests/helpers/` |

**Design history**

| Topic | Old location |
|---|---|
| Blueprint | `final_plan.md` (repo root) |
| Roadmap, phases, design decisions | `docs/roadmap.md`, `docs/phases/`, `docs/decisions/` |
