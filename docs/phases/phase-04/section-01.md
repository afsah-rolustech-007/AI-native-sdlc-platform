# Section 01 — ClaimSet, Evidence, and Spec Projection

## Objective

Define the typed objects the rest of the engine operates on: a `ClaimSet` extracted from the raw request, `Provenance` / `EvidenceRecord` for everything the engine believes, and a projection from those internal types onto §B.2 `RequirementsSpec` (the `TypedDict` already declared in `packages/orchestration/state.py`).

## Why It Exists

Literal §E.4 starts at `Question`. That forces a question-first loop. Evidence-first needs a structured representation of the *request* first, so later steps classify and retrieve against claims rather than re-sending prose to an LLM.

`RequirementsSpec` stays the **handoff** shape for Phase 05/`SDLCState`. It is a list of strings. The engine's working types are richer (status, source, evidence). Do **not** change `SDLCState.RequirementsSpec` in this phase.

## Expected Architecture

`packages/requirements_engine/claims.py` and `models.py`.

**Claim kind** (what it is about) is separate from **epistemic status** (how we know it):

| Kind | Maps toward §B.2 |
|---|---|
| `objective` | functional / assumptions |
| `functional` | `functional` |
| `constraint` | functional or NFR, depending on `nfr_type` |
| `nfr` | `non_functional[nfr_type]` |
| `acceptance` | `acceptance_criteria` |
| `out_of_scope` | `out_of_scope` |
| `repo_dependent` | stays internal until evidence or a decision resolves it |
| `unknown` | `open_ambiguities` until answered |

| Status | Meaning |
|---|---|
| `DECISION` | Explicit in the request or given by the engineer. Wins over repository facts. |
| `FACT` | Established by deterministic evidence (snapshot field, manifest, symbol hit, exact lexical identifier). |
| `INFERENCE` | Derived or weak retrieval (including **all semantic hits**). Never silently promoted to DECISION. |
| `UNKNOWN` | Not established. May activate a question slot. |
| `CONTRADICTION` | Two **explicit** requirements conflict (request vs later engineer answer, or two request claims). Repository PostgreSQL + user "use MongoDB" is **not** a contradiction — it is FACT + DECISION and may activate migration slots. |

`Provenance` records `source` (`request` \| `engineer` \| `repository` \| `derived` \| `assumption`), `ref` (path, symbol id, question id), `retrieved_via` (`snapshot` \| `symbol` \| `lexical` \| `graph` \| `semantic` \| `manifest` \| `none`), and `catalog_hash` at the time of retrieval.

**Structured extract** (`extract.py`): exactly one `ModelAdapter` call per session. Input is the raw request (and optional intake fields if the CLI supplies them). **Do not put the architecture summary in this prompt** — that mixes repository guesses into request claims. Prefer `call_tools` with a single `extract_claims` tool (Phase 02 already supports tool calling) over hoping `response_format` is honored. Validate with Pydantic. On parse failure: retry **once**, then fail closed by treating the request as unstructured (all high-value slots UNKNOWN), **never invent requirements**.

## Dependencies

Phase 02 (`ModelAdapter`). `orchestration.state.RequirementsSpec` as the emit target (import the TypedDict; do not fork it).

## Atomic Implementation Tasks

1. Implement `Claim`, `ClaimSet`, `Provenance`, `EvidenceRecord`, `EpistemicStatus`, `ClaimKind`.
2. Implement `extract_claims(request, adapter) -> ClaimSet` with schema validation and a single retry.
3. Implement `project_spec(claim_set, trace) -> RequirementsSpec` filling every §B.2 field (`version` starts at 1; `approved_at`/`approved_by` stay `None` until Phase 05/08).
4. Unit tests: projection of mixed DECISION/FACT/UNKNOWN; contradiction does not get dropped; extract parse failure does not emit fabricated functional requirements.
5. Do **not** call Repository Intelligence from this section.

## Manual Testing Procedure

1. Extract a well-specified request ("Add JWT refresh to the existing FastAPI auth module, keep PostgreSQL") and print the ClaimSet.
2. Extract a one-liner ("add auth") and confirm mostly `unknown` / `repo_dependent`, not invented NFRs.
3. Project both to `RequirementsSpec` JSON and confirm `open_ambiguities` is populated for the one-liner.

## Expected Demo

Terminal JSON of a ClaimSet next to its projected `RequirementsSpec`, with every claim showing kind, status, and provenance.

## Acceptance Criteria

- [ ] Claim kind and epistemic status are separate fields.
- [ ] Extract is repo-blind (no RI, no snapshot in the prompt).
- [ ] Projection emits a valid §B.2 `RequirementsSpec` without mutating `orchestration/state.py`.
- [ ] Malformed model output does not invent requirements.

## Risks

- **Risk:** The extract model infers repository facts from the request wording ("existing backend" → "therefore FastAPI"). **Mitigation:** repo-blind prompt; anything that needs the tree is `repo_dependent` + UNKNOWN until Section 03–05.

## Future Improvements

- Reconcile ClaimSet with Phase 10 `WorkflowContext` and Phase 05 Intent Tracker (`ADDITIVE` / `MODIFICATION` / `CONTRADICTION`).

## Research Opportunities

Which extract taxonomies correlate with fewer downstream design gaps — only answerable once Phase 15 has outcome data.
