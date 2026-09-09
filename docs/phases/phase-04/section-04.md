# Section 04 — EvidencePlan and Progressive Retrieval

## Objective

Give each activated slot a bounded, inspectable plan for how it may obtain repository evidence — and execute those plans with **targeted** RI calls, an in-session query cache, and a hard budget. Do not implement a learned router, RRF, or an unrestricted tool loop.

## Why It Exists

Literal section-03 mapped question ids to RI methods in an implied per-question call. Without a plan, the engine either over-fetches (semantic on every slot) or under-specifies (always `get_architecture_summary`). `EvidencePlan` makes exploration **budgeted and auditable** (Principle 5).

## Expected Architecture

Plans live on the question YAML (`evidence_plan`) so they are policy, not buried in Python. `plans.py` validates; `retrieve.py` executes.

```text
EvidencePlan:
  need: string                  # e.g. existing_auth_module
  methods:                      # ordered; stop when extractor accepts
    - signal: snapshot | manifest | symbol | lexical | graph | semantic
      # signal-specific fields: query, query_from_claims, symbol_id_from,
      # paths_from_snapshot, top_k, min_score, depth
      extractor: named deterministic extractor
      budget: int               # max RI calls for this method
  accept_as: fact | inference   # semantic may only be inference
  on_insufficient: ask_human | unknown
  max_ri_calls: int             # hard cap for the whole plan
```

### Progressive retrieval is **need-driven**, not a global ladder

A fixed Tier 0→5 pipeline is the wrong default: "does `AuthService` exist?" should not start at architecture JSON. Use this **cost preference** only when the plan's method list is empty (it should not be):

| Need | First signal | Then |
|---|---|---|
| Cheap situation ("languages?", "is there an `auth` service?") | snapshot / manifest | stop |
| "Does symbol X exist?" / signature | `get_symbol_signature` / `get_file_structure` | lexical name search |
| "Where is identifier JWT used?" | `search_codebase` | graph dependents of those files |
| "What is the blast radius of touching `auth/service.py`?" | `get_impact_set` / `get_dependents` | stop |
| "Code about session expiry" with no identifier | snapshot paths as `paths=` filter, then `search_concepts` | never FACT |

**Semantic search is last, optional, and weak.** Phase 03 benchmark is ~96% success@5 overall, lexical was **unscored** on the measuring machine, graph missed adversarial attribute-call resolution (`g06`). Semantic relatedness is not proof. `accept_as` for `semantic` is `inference` only. Defaults: `top_k=3`, `min_score` set, `paths` from snapshot when possible.

### Session retrieval cache

Key: `(signal, normalized_query, paths, kinds, catalog_hash)`. Reuse hits across slots. This is how the engine avoids asking RI the same question twice. Do **not** skip `assert_fresh` (Phase 03 contract). Accept that each **distinct** RI call still hashes the tree; the cache only prevents duplicate queries.

### Budgets and fail-closed signals

- Per-plan `max_ri_calls` and a session cap (config; start with 16).
- `ZoektUnavailableError` / `ZoektNotIndexedError`: mark lexical **unavailable**, skip that method, do not treat as zero hits.
- `EmbeddingsNotIndexedError`: skip semantic the same way.
- `SymbolNotFoundError`: evidence of absence **for that id**, not for the concept.
- `StaleIndexError`: stop retrieval, freeze auto-answer, surface to the caller.
- Never call `find_relevant_context`.

### Evidence records

Each call writes `EvidenceRecord`: signal, query, hit refs (path/symbol/line), excerpt (short), score if any, `catalog_hash`, latency, cache-hit flag. Traces are the silver labels Phase 15 needs for a future router. Emit `tool_call` telemetry via `TelemetrySink` when a sink is provided; tests may use `NoOpTelemetrySink`.

No LLM judge. Extractors are deterministic (JSON path on snapshot, symbol exists, lexical identifier in snippet, graph neighborhood non-empty). If an extractor cannot decide, status stays UNKNOWN.

## Dependencies

Section 02 (slots), Section 03 (snapshot), Phase 03 API.

## Atomic Implementation Tasks

1. YAML `evidence_plan` schema + validation (unknown signal = load error).
2. `execute_plan(plan, snapshot, ri, cache, claims) -> list[EvidenceRecord]`.
3. Named extractors in `auto_answer.py` (wired in Section 05; this section can stub the protocol).
4. Query cache + session RI budget.
5. Unit tests with fake RI: snapshot hit skips later methods; semantic never returned as FACT; Zoekt error skips lexical; cache prevents a second identical `search_codebase`.
6. Integration: one auth slot against the Phase 03 corpus uses snapshot and/or lexical, not semantic, to find `auth/service.py`.

## Manual Testing Procedure

1. Log every RI method name and arguments for the well-specified demo.
2. Confirm semantic is not called when snapshot already satisfied the plan.
3. Run with Zoekt missing: lexical slots skip, engine still exits fail-closed rather than "no JWT in repo."

## Expected Demo

A printed EvidencePlan execution trace: method, cache hit/miss, evidence refs, remaining budget.

## Acceptance Criteria

- [ ] Plans are config, validated at load.
- [ ] Semantic cannot produce FACT.
- [ ] Duplicate RI queries in one session are cached.
- [ ] Missing Zoekt/embeddings/stale index follow fail-closed contracts.
- [ ] `find_relevant_context` is never called.

## Risks

- **Risk:** Generic plans all fall through to semantic. **Mitigation:** bank review; tests that well-specified stack slots do not call `search_concepts`.

## Future Improvements

- Phase 15: train a retrieval-needed classifier on these traces.
- Phase 12: optional fusion **behind** RI, still not inside this engine.

## Research Opportunities

Per-need method order vs a single global escalation — log `plan.need` × `first_successful_signal` from day one.
