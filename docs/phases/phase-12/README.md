# Phase 12 — Context Engineering

## Goal

Reduce token consumption per task by at least 40% versus the Phase 11 baseline, with no drop in task success rate — by implementing the full context budget math (§H.1), the 5-step compression pipeline (§H.3), the personalized Aider-style PageRank repo map (§H.2: goal → seeds → PPR → L0.5) replacing Phase 03's placeholder, and real, token-capped Phase Handoff Packets (§B.5) replacing the raw artifact-passing used since Phase 05.

## Why This Phase Exists

Every agent since Phase 05 has been calling `RepositoryIntelligence` and passing artifacts between phases without a formal token budget or compression discipline — functionally correct, but not efficient. This phase is placed after Phase 11 (scale) specifically because token efficiency matters most exactly when repo/context size is largest — optimizing context budgets against a small fixture repo (Phase 03 scale) would under-motivate the real design decisions this phase requires.

## Dependencies

Phase 11 (a large-scale corpus and federated RI to measure token efficiency against meaningfully).

## High-Level Architecture

```
Every agent's context assembly (BaseAgent.build_context(), used since Phase 05)
        │
        ▼
  ContextBudget (§H.1) ── per-phase token allocations derived from model window
        │
        ▼
  Level 0: Architecture summary (unchanged since Phase 03 §06)
  Level 0.5: Personalized PageRank repo map (§H.2) ── goal/seeds → PPR → top-K; REPLACES Phase 03's placeholder
        │
        ▼
  Progressive context loading (§H.4) ── tool-based expansion, already used by
        │                                CodeGen since Phase 06 §05; now budget-aware
        ▼
  5-Step Compression Pipeline (§H.3) + tiered layout (§H.6) ── only engaged when over budget:
        T0 stable prefix (never)
        T1 Context Ledger + current WaveHandoffNote (never compressed)
        T2 working window (clear at wave boundary / 40% pressure)
        T3 anchored compacted history (wave boundary / 70% pressure)
        T4 Blackboard pointers
        │
        ▼
  Phase Handoff Packet (§B.5) + wave→wave WaveHandoffNote (2,000 tokens)
```

## Expected Live Demo

Run the Phase 06 demo feature (or an equivalent representative task) twice against the Phase 11-scale corpus: once with context engineering disabled (Phase 11's raw behavior) and once with it fully enabled, measuring total tokens consumed for an equivalent, successfully-completed task. Show the ≥40% reduction, and show the task still succeeds (same QA outcome) under compression — proving efficiency without accuracy loss.

## Deliverables

- `packages/context_engine/budget.py`, `builder.py`, `compressor.py`, `handoff_packet.py`.
- Real **personalized** Aider-style PageRank repo map (seeded from task goal/input), replacing Phase 03's heuristic placeholder.
- Real, token-capped `PhaseHandoffPacket` at every phase transition.
- `compact_at_wave_close` wired from Fan-in (replaces Phase 06 no-op stub; §D.4.0.1 / §H.6).

## Sections

1. [Context Budget Math per Phase](section-01.md)
2. [Aider-Style PageRank Repo Map](section-02.md)
3. [5-Step Compression Pipeline](section-03.md)
4. [Real Phase Handoff Packets](section-04.md)
5. [Token Efficiency Benchmark](section-05.md)
