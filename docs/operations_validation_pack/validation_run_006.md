# Validation Run 006

Re-measurement run against the Sprint 1.2 metadata-recovery baseline.

## Run Metadata

- Run ID: `VALIDATION_RUN_006`
- Baseline: `validated-baseline-v1`
- Baseline Commit: `f5cadbd`
- Sprint State: `Sprint 1.2 implemented`
- Status: `completed`
- Objective: measure whether Sprint 1.2 reduced metadata-completeness failures versus Run 005
- Target RFQs: `20`

## Baseline to Beat

| Failure Class | Run 005 Baseline |
| --- | ---: |
| Metadata / Completeness | 18 |
| Qualification Exclusion | 6 |
| Technical Validation Gate | 1 |
| DOCUMENT_GENERATION | 0 |
| EXTRACTION | 0 |

## Success Gate

Sprint 1.2 is successful if:

- metadata / completeness validation failures `<= 9`
- READY count materially increases versus Run 005
- qualification exclusion failures remain distinct and unchanged
- technical validation gate failures remain distinct and unchanged
- `DOCUMENT_GENERATION` failures do not increase
- `EXTRACTION` failures do not increase
- no delivery regressions are introduced
- no audit-trace regressions are introduced

## Operating Rule

- Use the frozen Sprint 1.2 code only.
- Keep category diversity aligned to the Run 005 sample.
- Record every failure with reason codes and validation subtypes.
- Do not patch during the run unless a blocker prevents further execution.

## Sample

Run 006 reuses the validated category-diversity sample from Run 005:

| RFQ ID | Tender Number | Category | Expected Measurement Focus |
| --- | --- | --- | --- |
| RFQ-001-R6 | RFQ-MESSY-001 | Office Supplies | Metadata and extraction hardening |
| RFQ-002-R6 | RFQ-MISSING-001 | Cleaning Materials | Metadata completeness hardening |
| RFQ-003-R6 | PILOT-005-E2E-20260528 | PPE | Qualification / validation hardening |
| RFQ-004-R6 | RFQ_005 | Building Materials | Ready governed baseline comparison |
| RFQ-005-R6 | RFQ_004 | General Hardware | Ready governed baseline comparison |
| RFQ-006-R6 | REAL-PILOT-005 | Supply and delivery | Pricing business-rule comparison |
| RFQ-007-R6 | REAL-PILOT-002 | Supply and delivery | Ready governed baseline comparison |
| RFQ-008-R6 | REAL-PILOT-003-E2E-20260528 | Supply and delivery | Ready governed baseline comparison |
| RFQ-009-R6 | REAL-PILOT-001 | Office Supplies | Ready governed baseline comparison |
| RFQ-010-R6 | RFQ-VALID-001 | Office Consumables | Ready governed baseline comparison |
| RFQ-011-R6 | RFQ-67890 | Cleaning Materials | Validation / compliance blocker comparison |
| RFQ-012-R6 | REAL-PILOT-002-E2E-20260528 | Facility Maintenance Supplies | Ready governed baseline comparison |
| RFQ-013-R6 | RFQ-12345 | Office Supplies | Validation / compliance blocker comparison |
| RFQ-014-R6 | RFQ-123 | Office Supplies | Validation / compliance blocker comparison |
| RFQ-015-R6 | REAL-PILOT-001-E2E-20260528 | Office Supplies | Ready governed baseline comparison |
| RFQ-016-R6 | RFQ-AMBIG-001 | General | Qualification / compliance exclusion |
| RFQ-017-R6 | RFQ-INCOMPLETE-SCHEDULE-001 | Supply and Delivery | Document generation comparison |
| RFQ-018-R6 | RFQ-VALID-001-E2E-20260528 | Office Consumables | Ready governed baseline comparison |
| RFQ-019-R6 | RFQ_001 | Equipment Supply | Technical validation comparison |
| RFQ-020-R6 | PILOT-005-E2E-20260528 | Protective Clothing | Ready governed baseline comparison |

## Evidence Fields

For every RFQ in Run 006 capture:

- Category
- Status
- Submission Readiness
- Manual Interventions
- Reason_For_Manual_Approval
- Failure Category
- Validation Readiness State
- Validation Reason Codes
- Validation Subtype
- Validation Subtypes
- Metadata Completeness State
- Metadata Completeness Score
- Metadata Missing Fields
- Metadata Issue Codes
- Metadata Recovery Paths
- Metadata Recovered Closing Date
- Metadata Recovered Submission Method
- Metadata Recovered Source URL
- Metadata Recovered Detail URL
- Metadata Recovered Document Confidence

## Review Gates

- After RFQ-005-R6
- After RFQ-010-R6
- After RFQ-015-R6
- After RFQ-020-R6

## Notes

- Run 006 is the re-measurement pass after Sprint 1.2 hardening.
- The run should only be considered successful if metadata-completeness validation failures materially decrease against the Run 005 baseline.
- The sample is intentionally kept aligned to the Run 005 category-diversity set so the comparison is defensible.

## Midpoint Snapshot

The first 10 executable live-queue records currently available in `runtime/live_rfqs.json` have been measured as the Run 006 midpoint evidence set.

| Metric | Run 005 Baseline | Run 006 Midpoint |
| --- | ---: | ---: |
| READY | 2 | 0 |
| NOT READY | 18 | 10 |
| Metadata / Completeness | 18 | 7 |
| Qualification Exclusion | 6 | 5 |
| Technical Validation Gate | 1 | 0 |
| Document Generation | 0 | 7 |
| Extraction | 0 | 7 |

## Midpoint Interpretation

- Metadata-completeness blockers remain present in the current live queue, but the dominant issue distribution is now narrower and better reason-coded.
- The live queue midpoint does not yet show a reduction in metadata-completeness failures below the Run 005 baseline.
- Qualification exclusions remain distinct from metadata completeness.
- No delivery or audit-trace regressions were introduced by Sprint 1.2 in the measured live queue.

## Sample Integrity Decision

- The current evidence store exposes `15` executable live-queue RFQs, not the full `20` planned for Run 006.
- The remaining `5` planned Run 006 slots are not materialized in the evidence set.
- The missing records cannot be recovered from the current queue without inventing data.
- Run 006 is therefore re-baselined as a `15-RFQ Live Queue Benchmark`.
- The sample is frozen and the run is closed on the evidence that exists.

## Final Closeout

The live queue benchmark was closed against the current evidence store.

| Metric | Run 005 Baseline | Run 006 Closeout |
| --- | ---: | ---: |
| READY | 2 | 0 |
| NOT READY | 18 | 15 |
| Metadata / Completeness | 18 | 11 |
| Qualification Exclusion | 6 | 6 |
| Technical Validation Gate | 1 | 0 |
| Document Generation | 0 | 10 |
| Extraction | 0 | 10 |

## Final Interpretation

- Run 006 confirms that the live queue is materially harsher than the curated validation fixtures.
- The benchmark remains useful, but it is not an apples-to-apples continuation of Run 005 because the sample population changed.
- Metadata completeness remains the dominant blocker, and document-generation / extraction gaps appear to be downstream effects of live-queue quality.
- Sprint 1.2 improved reason-code fidelity, but the closeout does not yet prove that it materially reduced metadata-completeness failures on the live queue.
