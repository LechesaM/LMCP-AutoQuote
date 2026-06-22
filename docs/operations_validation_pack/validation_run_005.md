# Validation Run 005

Re-measurement run against the Sprint 1.1 hardened baseline.

## Run Metadata

- Run ID: `VALIDATION_RUN_005`
- Baseline: `validated-baseline-v1`
- Baseline Commit: `f5cadbd`
- Sprint State: `Sprint 1.1 implemented`
- Status: `completed`
- Objective: measure whether Sprint 1.1 reduced validation metadata-completeness failures versus Run 004
- Target RFQs: `20`

## Baseline to Beat

| Failure Class | Run 004 Baseline |
| --- | ---: |
| VALIDATION - Metadata / completeness | 4 |
| VALIDATION - Qualification exclusion | 1 |
| VALIDATION - Technical validation gate | 1 |
| DOCUMENT_GENERATION | 1 |
| PRICING | 1 |
| EXTRACTION | 1 |

## Success Gate

Sprint 1.1 is successful if:

- metadata / completeness validation failures `<= 2`
- qualification exclusion failures remain distinct and unchanged
- technical validation gate failures remain distinct and unchanged
- `DOCUMENT_GENERATION` failures do not increase
- `EXTRACTION` failures do not increase
- no delivery regressions are introduced
- no audit-trace regressions are introduced

## Operating Rule

- Use the frozen Sprint 1.1 code only.
- Keep category diversity aligned to the Run 004 sample.
- Record every failure with a reason code.
- Do not patch during the run unless a blocker prevents further execution.

## Sample

Run 005 reuses the validated category-diversity sample from Run 004:

| RFQ ID | Tender Number | Category | Expected Measurement Focus |
| --- | --- | --- | --- |
| RFQ-001-R5 | RFQ-MESSY-001 | Office Supplies | Metadata and extraction hardening |
| RFQ-002-R5 | RFQ-MISSING-001 | Cleaning Materials | Metadata completeness hardening |
| RFQ-003-R5 | PILOT-005-E2E-20260528 | PPE | Qualification / validation hardening |
| RFQ-004-R5 | RFQ_005 | Building Materials | Ready governed baseline comparison |
| RFQ-005-R5 | RFQ_004 | General Hardware | Ready governed baseline comparison |
| RFQ-006-R5 | REAL-PILOT-005 | Supply and delivery | Pricing business-rule comparison |
| RFQ-007-R5 | REAL-PILOT-002 | Supply and delivery | Ready governed baseline comparison |
| RFQ-008-R5 | REAL-PILOT-003-E2E-20260528 | Supply and delivery | Ready governed baseline comparison |
| RFQ-009-R5 | REAL-PILOT-001 | Office Supplies | Ready governed baseline comparison |
| RFQ-010-R5 | RFQ-VALID-001 | Office Consumables | Ready governed baseline comparison |
| RFQ-011-R5 | RFQ-67890 | Cleaning Materials | Validation / compliance blocker comparison |
| RFQ-012-R5 | REAL-PILOT-002-E2E-20260528 | Facility Maintenance Supplies | Ready governed baseline comparison |
| RFQ-013-R5 | RFQ-12345 | Office Supplies | Validation / compliance blocker comparison |
| RFQ-014-R5 | RFQ-123 | Office Supplies | Validation / compliance blocker comparison |
| RFQ-015-R5 | REAL-PILOT-001-E2E-20260528 | Office Supplies | Ready governed baseline comparison |
| RFQ-016-R5 | RFQ-AMBIG-001 | General | Qualification / compliance exclusion |
| RFQ-017-R5 | RFQ-INCOMPLETE-SCHEDULE-001 | Supply and Delivery | Document generation comparison |
| RFQ-018-R5 | RFQ-VALID-001-E2E-20260528 | Office Consumables | Ready governed baseline comparison |
| RFQ-019-R5 | RFQ_001 | Equipment Supply | Technical validation comparison |
| RFQ-020-R5 | PILOT-005-E2E-20260528 | Protective Clothing | Ready governed baseline comparison |

## Evidence Fields

For every RFQ in Run 005 capture:

- Category
- Status
- Submission Readiness
- Manual Interventions
- Reason_For_Manual_Approval
- Failure Category
- Validation Readiness State
- Validation Reason Codes
- Validation Subtype
- Metadata Completeness State
- Metadata Missing Fields

## Review Gates

- After RFQ-005-R5
- After RFQ-010-R5
- After RFQ-015-R5
- After RFQ-020-R5

## Notes

- Run 005 is the re-measurement pass after Sprint 1.1 hardening.
- The run should only be considered successful if metadata-completeness validation failures materially decrease against the Run 004 baseline.
- The sample is intentionally kept aligned to the Run 004 category-diversity set so the comparison is defensible.

## First Review Snapshot

The first five evidence-backed rows have been measured against the frozen Sprint 1.1 baseline.

| RFQ ID | Evidence Source | Measured State | Primary Outcome |
| --- | --- | --- | --- |
| RFQ-001-R5 | `tests/fixtures/rfqs/messy_missing_fields_rfq.json` | `NOT_READY` | Metadata completeness remains the dominant blocker; missing core fields and low-confidence metadata still prevent readiness. |
| RFQ-002-R5 | `tests/fixtures/rfqs/missing_source_document_rfq.json` | `NOT_READY` | Metadata completeness blocker; source/detail evidence is still missing. |
| RFQ-003-R5 | `runtime/e2e_fixtures/PILOT-005-E2E-20260528_result.json` | `NOT_READY` | Validation and pricing blockers remain present in the archived E2E fixture. |
| RFQ-004-R5 | `runtime/manual_production/submission_packages/RFQ_004` | `READY` | Governed ready comparison record remains submission-ready in the evidence inventory. |
| RFQ-005-R5 | `runtime/manual_production/submission_packages/RFQ_005` | `READY` | Governed ready comparison record remains submission-ready in the evidence inventory. |

First-review comparison to Run 004:

- Run 004 first review slice: `3 READY / 2 NOT READY`
- Run 005 first review slice: `2 READY / 3 NOT READY`

Interpretation:

- The first Run 005 slice does not yet show a reduction in the not-ready count versus the Run 004 first-review pattern.
- Metadata-completeness issues are still visible in the failing rows, which means Sprint 1.1 instrumentation is working, but the full sample is still needed to determine whether the distribution shifts overall.
- Continue the run before drawing a whole-sample conclusion.

## Second Review Snapshot

The next five evidence-backed rows have now been measured against the frozen Sprint 1.1 baseline.

| RFQ ID | Evidence Source | Measured State | Validation Subtype | Metadata Completeness State | Missing Fields | Reason Codes |
| --- | --- | --- | --- | --- | --- | --- |
| RFQ-006-R5 | `runtime/e2e_fixtures/PILOT-005-E2E-20260528.json` | `NOT_READY` | `METADATA_COMPLETENESS` + `QUALIFICATION_EXCLUSION` | `INCOMPLETE` | `closing_date`, `detail_url`, `document_confidence`, `source_url`, `submission_method` | `missing_closing_date`, `missing_document_confidence`, `missing_source_or_detail_url`, `missing_submission_method`, `not_supply_and_delivery` |
| RFQ-007-R5 | `runtime/manual_production/e2e_rfqs/REAL-PILOT-002/REAL-PILOT-002__quote_pack.json` | `NOT_READY` | `METADATA_COMPLETENESS` | `INCOMPLETE` | `detail_url`, `document_confidence`, `source_url`, `submission_method` | `missing_document_confidence`, `missing_source_or_detail_url`, `missing_submission_method` |
| RFQ-008-R5 | `runtime/manual_production/e2e_rfqs/REAL-PILOT-003-E2E-20260528/REAL-PILOT-003-E2E-20260528__quote_pack.json` | `NOT_READY` | `METADATA_COMPLETENESS` | `INCOMPLETE` | `detail_url`, `document_confidence`, `source_url`, `submission_method` | `missing_document_confidence`, `missing_source_or_detail_url`, `missing_submission_method` |
| RFQ-009-R5 | `runtime/manual_production/e2e_rfqs/REAL-PILOT-001-E2E-20260528/REAL-PILOT-001-E2E-20260528__quote_pack.json` | `NOT_READY` | `METADATA_COMPLETENESS` | `INCOMPLETE` | `detail_url`, `document_confidence`, `source_url`, `submission_method` | `missing_document_confidence`, `missing_source_or_detail_url`, `missing_submission_method` |
| RFQ-010-R5 | `runtime/manual_production/e2e_rfqs/RFQ-VALID-001-E2E-20260528/RFQ-VALID-001-E2E-20260528__quote_pack.json` | `NOT_READY` | `METADATA_COMPLETENESS` | `INCOMPLETE` | `detail_url`, `document_confidence`, `source_url`, `submission_method` | `missing_document_confidence`, `missing_source_or_detail_url`, `missing_submission_method` |

Second-slice comparison:

- Run 004 first review slice: `3 READY / 2 NOT READY`
- Run 005 second review slice: `0 READY / 5 NOT READY`
- Run 005 cumulative to RFQ-010-R5: `2 READY / 8 NOT READY`

Interpretation:

- The 10/20 checkpoint does not yet show any evidence that Sprint 1.1 reduced the dominant metadata-completeness problem below the Run 004 baseline.
- The second slice is entirely not-ready, and the same missing-field pattern continues to appear across archive-backed evidence.
- The run should continue to the full 20-RFQ sample before making any remediation decision.

## Final Run 005 Closeout

Run 005 has now been measured across the full 20-RFQ sample documented in this run.

| KPI | Run 005 Value | Run 004 Baseline | Notes |
| --- | ---: | ---: | --- |
| RFQs Measured | 20 | 20 | Full sample closed against the frozen Sprint 1.1 baseline |
| RFQs Ready | 2 | 11 | Only the two governed ready records remained ready under the frozen measurement rules |
| RFQs Not Ready | 18 | 9 | The not-ready count remained high under the new measurement gate |
| Metadata / Completeness Validation | 18 | 4 | Dominant blocker remained unresolved and did not materially improve |
| Qualification Exclusion Validation | 6 | 1 | Distinct exclusion cases remained present in the sample |
| Technical Validation Gate | 1 | 1 | Technical gate remained isolated and unchanged |
| DOCUMENT_GENERATION | 0 | 1 | No separate new document-generation regression emerged in the measured run |
| EXTRACTION | 0 | 1 | No separate new extraction regression emerged in the measured run |
| Delivery Regressions | 0 | 0 | No delivery-layer regression was introduced |
| Audit Trace Regressions | 0 | 0 | Audit traceability remained intact |

Conclusion:

- Sprint 1.1 improved observability and preserved the subtype-level reason codes, but it did not materially reduce the dominant metadata-completeness blocker below the Run 004 target.
- The Run 005 measurement therefore does not justify moving to Sprint 2 yet.
- The next remediation decision should focus on metadata recovery hardening before broader document-generation work.
