# Section 02 — Evidence Bundle Generator

## Objective

Implement the evidence bundle standard (§K.5) that assembles everything a human approver needs to make a decision at `ApprovalGate`(pr)/(deployment): coverage delta, static analysis results, security findings, test results, spec compliance, bug reproduction result (if applicable), and risk score — sourced from the real `QAEvidence` Phase 07 now produces.

## Why It Exists

An `ApprovalGate` that shows a human a wall of raw logs isn't actually enabling good decisions — it's transferring cognitive load without adding value. A structured, consistent evidence bundle is what makes human approval fast *and* well-informed, which matters a lot once a human is approving many tasks a day (a real scaling concern for HITL rate KPIs, §L.2).

## Expected Architecture

`packages/qa/evidence_collector.py`'s `build_evidence_bundle(task_id) -> EvidenceBundle` assembles the §K.5 fields from `QAEvidence` (Phase 07), the diff (Phase 06), `RequirementsSpec` (Phase 05), and confidence breakdown (Phase 04 §04) into one structured object, persisted to the blackboard (an artifact store — implement this now as a simple table/object-storage pattern if it doesn't already exist implicitly; document the choice) and referenced by pointer from `ApprovalGate` payloads (per §B.5's "rationale_ref = blackboard pointer, not inlined" principle, applied here to evidence bundles too).

## Dependencies

Phase 07 (full `QAEvidence`), Phase 06 (diff), Phase 04 §04 (confidence breakdown).

## Atomic Implementation Tasks

1. Define the `EvidenceBundle` schema per §K.5's exact field list.
2. Implement the blackboard/artifact-store pattern if not already established — a simple content-addressed or task-scoped storage (Postgres JSONB column or a dedicated table is sufficient at this scale; object storage is a future-scale concern, not needed now).
3. Implement `build_evidence_bundle()` assembling all fields from real upstream data (no placeholder/fake fields at this phase — everything referenced in §K.5 has a real source by Phase 07).
4. Wire evidence bundle construction into `ApprovalGate`(pr)'s and `ApprovalGate`(deployment)'s `evidence_bundle_spec`, replacing Phase 05's minimal placeholder bundle.
5. Integration test: build an evidence bundle for the demo feature's completed task and verify every field is populated with real, correct data (not a null/placeholder) by cross-checking against the underlying `QAEvidence`/diff/spec records.

## Manual Testing Procedure

1. Run the demo feature through to `ApprovalGate`(pr) and print the full evidence bundle exactly as a human approver would see it.
2. Manually review it for completeness and clarity — would a human unfamiliar with the task's internals be able to make an informed decision from this alone?
3. Confirm the bundle is stored via pointer reference in the `interrupt()` payload, not inlined in full (verify payload size stays small even though the underlying bundle can be large).

## Expected Demo

The printed evidence bundle from the manual test above — this is effectively a preview of Phase 09's Screen 8 (Human Approval Requests) before any UI exists to render it.

## Acceptance Criteria

- [ ] `EvidenceBundle` includes every field named in §K.5, all sourced from real data.
- [ ] Evidence bundles are stored via blackboard pointer, not inlined into `interrupt()` payloads — verified by inspecting payload size/shape.
- [ ] A human reviewer (informally, yourself) judges the bundle sufficient to make an approval decision without needing to dig through raw logs separately.

## Risks

- **Risk:** An evidence bundle that's too terse omits decision-relevant detail; too verbose defeats its own purpose. **Mitigation:** treat this as subject to revision based on real usage — this is exactly the kind of UX-adjacent judgment call worth revisiting once Phase 09's UI makes the bundle visually consumable and real approval friction (or lack thereof) becomes observable.

## Future Improvements

- Richer bundles incorporating security/mutation findings (Phase 13) and precedent-task comparisons (once episodic memory is richer, post Phase 06+ accumulation).

## Research Opportunities

None yet — becomes relevant once real approval-time metrics (time-to-decision, rejection rate) exist from Phase 09's UI and Phase 15's evaluation.
