# Phase 16 — Production Hardening

## Goal

Close out every risk mitigation deferred throughout the roadmap (§N) so the platform is genuinely production-ready: eliminate remaining single points of failure, prove concurrency/multi-tenant safety, enforce the full RBAC model (§S) in the backend (not just presentation-layer filtering), lock down the security model end to end (§B.6), and validate cost/scalability limits under realistic load. This is the final phase — no new capabilities, only hardening what already exists.

## Why This Phase Exists

Every prior phase built one capability at a time against a single-engineer, mostly-single-tenant development context. Production readiness is cross-cutting by nature and cannot be meaningfully verified until the full system exists (Phases 00–15) and has been exercised by Phase 15's evaluation framework. This phase is deliberately last and deliberately not split into further build phases — it is a hardening and verification pass, not new architecture.

## Dependencies

All prior phases (00–15). This phase modifies existing code for robustness; it does not introduce new components.

## High-Level Architecture

No new components are introduced. This phase audits and hardens existing seams:

```
┌─────────────────────────────────────────────────────────────┐
│  Existing System (Phases 00-15)                              │
│                                                                │
│  Reliability & SPOF          Concurrency & Multi-Tenancy      │
│  - DB failover               - Row-level locking on shared    │
│  - Checkpointer HA             resources (RI index, budgets)  │
│  - Circuit breaker review     - Per-tenant resource isolation │
│                                                                │
│  Security Lockdown            RBAC Enforcement (backend)      │
│  - Secrets audit              - §S roles enforced at API      │
│  - Sandbox escape testing       layer, not just UI            │
│  - Credential scoping audit   - Audit log for all RBAC checks │
│                                                                │
│  Cost & Scale Validation                                      │
│  - Load testing at target concurrent-task volume              │
│  - Cost-ceiling stress testing (kill-switch under load)       │
└─────────────────────────────────────────────────────────────┘
```

## Expected Live Demo

A single hardening report covering: (1) a chaos test killing the database mid-task and showing clean recovery via checkpointing (extending Phase 01 §04's harness to Postgres itself, not just the worker), (2) two concurrent tasks from different simulated tenants proven isolated from each other's budgets and RI index access, (3) an RBAC test showing a `viewer`-role API call correctly rejected at the backend even if the UI were bypassed, (4) a load test report at the target concurrent-task volume with cost kill-switch correctly triggering under simulated budget exhaustion.

## Deliverables

- `tests/chaos/test_db_failover.py` extending Phase 01 §04's crash-recovery harness.
- `tests/multitenancy/test_isolation.py` proving budget and RI index isolation across simulated tenants.
- Backend RBAC middleware enforcing §S at every API route, with an audit log.
- `tests/load/production_load_test.py` (Locust) and a documented cost kill-switch stress test.
- A final production-readiness report mapping every §N risk category to its concrete mitigation and test evidence.

## Atomic Implementation Tasks

1. Extend Phase 01 §04's crash-recovery harness to kill the Postgres container mid-task (not just the worker process) and verify checkpoint-based recovery once the DB returns, using the same host's Docker-based test setup.
2. Audit the `CircuitBreaker` (Phase 02 §04) and `ModelRouter` for any remaining single-provider hard dependency; add a documented manual failover path if a second provider is not yet configured.
3. Implement row-level locking or equivalent isolation for shared mutable resources accessed concurrently (RI index writes, budget ledger updates) and write a test running two tasks concurrently against the same resource to prove no cross-task interference.
4. Move RBAC enforcement (§S) from Phase 09 §05's presentation-layer filtering into real backend middleware on every FastAPI route, rejecting unauthorized requests with a 403 and logging the attempt.
5. Run a credential/secrets audit across every component that touches credentials (sandbox, git adapters, MCP clients, model adapters) confirming no standing production credentials and correct scoping/redaction per §B.6.
6. Attempt a sandbox escape test (e.g., an agent-generated script trying to reach the network or host filesystem) against Phase 00 §04's sandbox and confirm it is blocked.
7. Run a load test at a realistic target concurrent-task volume (define the target explicitly, e.g., 20 concurrent tasks) and record latency/throughput/error-rate results.
8. Run a cost kill-switch stress test: simulate multiple tasks approaching budget ceilings simultaneously and confirm the kill-switch (Phase 00 §03) correctly halts affected tasks without affecting unrelated ones.
9. Write the final production-readiness report mapping each §N risk category (reliability, scalability, SPOF, concurrency, cost, security, operational) to its concrete mitigation and the test evidence produced by tasks 1–8.

## Manual Testing Procedure

Execute each of the eight test tasks above against a staging-like environment and manually review results against the criteria in each task before compiling the final report.

## Acceptance Criteria

- [ ] DB failover recovery succeeds without data loss or duplicate side effects.
- [ ] Concurrent multi-tenant tasks show zero cross-tenant interference in budgets or RI index access.
- [ ] Backend RBAC middleware rejects unauthorized API calls regardless of UI state.
- [ ] Secrets/credential audit finds no standing production credentials and confirms correct scoping.
- [ ] Sandbox escape test is blocked.
- [ ] Load test meets the documented target concurrent-task volume without unacceptable error rate.
- [ ] Cost kill-switch correctly triggers under simulated budget exhaustion without affecting unrelated tasks.
- [ ] Every §N risk category has documented mitigation and test evidence in the final report.

## Risks

Production hardening can reveal architectural issues that are expensive to fix this late — mitigated by the roadmap's consistent Fail-Closed-first, sandboxed-by-default approach from Phase 00 onward, which should mean this phase mostly *proves* rather than *creates* safety.

## Future Improvements

Multi-region deployment, formal penetration testing by a third party, SOC2-style compliance audit — explicitly out of scope for this roadmap and left as follow-on work once the platform has real production usage to justify the investment.
