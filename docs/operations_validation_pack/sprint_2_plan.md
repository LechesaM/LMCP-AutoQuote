# Sprint 2 - Document Generation Hardening

## Status

- Approved for planning
- Implementation not started
- Validation gate: `Validation Run 008`

## Evidence Basis

- Run 006 live benchmark showed document-generation and extraction gaps alongside metadata-completeness issues.
- Run 007 showed metadata recovery can improve READY outcomes, but the remaining live-queue benchmark still contains document-quality blockers.
- Sprint 2 focuses on the downstream document-pack defects that remain after metadata recovery has been applied.

## Objective

Reduce document-generation-caused `NOT_READY` outcomes for otherwise eligible opportunities.

## Scope

Focus on:

- document completeness validation
- pricing schedule generation robustness
- returnables generation robustness
- annexure handling
- mandatory attachment packaging
- document quality scoring
- submission-pack completeness

## Out of Scope

- qualification rules
- metadata recovery logic
- delivery workflow
- audit-trace workflow
- supplier network expansion
- BOQ mapping redesign

## Target Failure Types

- incomplete schedules
- missing pricing rows
- missing mandatory attachments
- incomplete annexure bundles
- submission-pack completeness gaps

## Acceptance Criteria

- document-generation-caused `NOT_READY` outcomes materially decrease against the Run 006 live-queue benchmark
- READY count holds or improves
- no delivery regressions are introduced
- no audit-trace regressions are introduced

## Validation Gate

- Implement Sprint 2
- Run `Validation Run 008`
- Compare directly against the Run 006 live-queue benchmark

## Notes

- Sprint 2 should be treated as the next engineering sprint only after the metadata-recovery work has proven it can convert READY outcomes on the live queue.
- The plan is intentionally constrained to document-completeness work so the next measurement run remains defensible.
