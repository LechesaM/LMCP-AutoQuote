# Validation Run 004

Measurement run against the Sprint 1 hardened baseline.

## Run Metadata

- Run ID: `VALIDATION_RUN_004`
- Baseline: `validated-baseline-v1`
- Baseline Commit: `f5cadbd`
- Sprint State: `Sprint 1 implemented`
- Status: `complete`
- Objective: measure whether Sprint 1 reduced validation failures versus Run 002
- Target RFQs: `20`

## Baseline to Beat

| Failure Class | Run 002 Baseline |
| --- | ---: |
| VALIDATION | 6 |
| DOCUMENT_GENERATION | 2 |
| PRICING | 2 |
| EXTRACTION | 1 |

## Success Gate

Sprint 1 is successful if:

- `VALIDATION` failures `<= 3`
- `DOCUMENT_GENERATION` failures do not increase
- `EXTRACTION` failures do not increase
- no delivery regressions are introduced
- no audit-trace regressions are introduced

## Operating Rule

- Use the frozen Sprint 1 code only.
- Keep category diversity aligned to the Run 002 sample.
- Record every failure with a reason code.
- Do not patch during the run unless a blocker prevents further execution.

## Sample

Run 004 reuses the validated category-diversity sample from Run 002:

| RFQ ID | Tender Number | Category | Expected Measurement Focus |
| --- | --- | --- | --- |
| RFQ-001-R4 | RFQ-MESSY-001 | Office Supplies | Validation and extraction hardening |
| RFQ-002-R4 | RFQ-MISSING-001 | Cleaning Materials | Document completeness hardening |
| RFQ-003-R4 | PILOT-005-E2E-20260528 | PPE | Qualification / validation hardening |
| RFQ-004-R4 | RFQ_005 | Building Materials | Ready governed baseline comparison |
| RFQ-005-R4 | RFQ_004 | General Hardware | Ready governed baseline comparison |
| RFQ-006-R4 | REAL-PILOT-005 | Supply and delivery | Pricing business-rule comparison |
| RFQ-007-R4 | REAL-PILOT-002 | Supply and delivery | Ready governed baseline comparison |
| RFQ-008-R4 | REAL-PILOT-003-E2E-20260528 | Supply and delivery | Ready governed baseline comparison |
| RFQ-009-R4 | REAL-PILOT-001 | Office Supplies | Ready governed baseline comparison |
| RFQ-010-R4 | RFQ-VALID-001 | Office Consumables | Ready governed baseline comparison |
| RFQ-011-R4 | RFQ-67890 | Cleaning Materials | Validation / compliance blocker comparison |
| RFQ-012-R4 | REAL-PILOT-002-E2E-20260528 | Facility Maintenance Supplies | Ready governed baseline comparison |
| RFQ-013-R4 | RFQ-12345 | Office Supplies | Validation / compliance blocker comparison |
| RFQ-014-R4 | RFQ-123 | Office Supplies | Validation / compliance blocker comparison |
| RFQ-015-R4 | REAL-PILOT-001-E2E-20260528 | Office Supplies | Ready governed baseline comparison |
| RFQ-016-R4 | RFQ-AMBIG-001 | General | Qualification / compliance exclusion |
| RFQ-017-R4 | RFQ-INCOMPLETE-SCHEDULE-001 | Supply and Delivery | Document generation comparison |
| RFQ-018-R4 | RFQ-VALID-001-E2E-20260528 | Office Consumables | Ready governed baseline comparison |
| RFQ-019-R4 | RFQ_001 | Equipment Supply | Technical validation comparison |
| RFQ-020-R4 | PILOT-005-E2E-20260528 | Protective Clothing | Ready governed baseline comparison |

## Evidence Fields

For every RFQ in Run 004 capture:

- Category
- Status
- Submission Readiness
- Manual Interventions
- Reason_For_Manual_Approval
- Failure Category
- Validation Readiness State
- Validation Reason Codes

## Review Gates

- After RFQ-005-R4
- After RFQ-010-R4
- After RFQ-015-R4
- After RFQ-020-R4

## Notes

- Run 004 is the first measurement pass after Sprint 1 hardening.
- The run should only be considered successful if the validation failure count materially decreases against the Run 002 baseline.
- The sample is intentionally kept aligned to the Run 002 category-diversity set so the comparison is defensible.

## First Review Snapshot

The first five evidence-backed rows have now been measured against the frozen Sprint 1 baseline.

| RFQ ID | Evidence Source | Measured State | Primary Outcome |
| --- | --- | --- | --- |
| RFQ-001-R4 | `tests/fixtures/rfqs/messy_missing_fields_rfq.json` | `NOT_READY` | Extraction-heavy blocker; missing core fields remain unresolved |
| RFQ-002-R4 | `tests/fixtures/rfqs/missing_source_document_rfq.json` | `NOT_READY` | Validation blocker; source/detail evidence still missing |
| RFQ-003-R4 | `runtime/e2e_fixtures/PILOT-005-E2E-20260528_result.json` | `READY` | Archive-backed proof-recorded fixture remains stable |
| RFQ-004-R4 | `runtime/manual_production/submission_packages/RFQ_005` | `READY` | Submission pack and quote pack evidence remain intact |
| RFQ-005-R4 | `runtime/manual_production/submission_packages/RFQ_004` | `READY` | Submission pack and quote pack evidence remain intact |

First-review comparison to Run 002:

- Run 002 first review slice: `2 READY / 3 NOT READY`
- Run 004 first review slice: `3 READY / 2 NOT READY`

Interpretation:

- Sprint 1 has not eliminated validation blockers, but the first Run 004 slice is currently better than the Run 002 first-review pattern.
- The ready half remains stable and does not show a pricing or document-generation regression in this slice.
- Continue the run before drawing a whole-sample conclusion.

## Completion Summary

Run 004 has now been measured across the full 20-RFQ sample documented in this run.

| KPI | Run 004 Value | Run 002 Baseline |
| --- | ---: | ---: |
| RFQs Measured | 20 | 20 |
| Ready | 11 | 9 |
| Not Ready | 9 | 11 |
| VALIDATION failures | 6 | 6 |
| DOCUMENT_GENERATION failures | 1 | 2 |
| PRICING failures | 1 | 2 |
| EXTRACTION failures | 1 | 1 |
| SUPPLIER failures | 0 | 0 |
| BOQ_MAPPING failures | 0 | 0 |

Interpretation:

- Sprint 1 improved the ready count, but it did not reduce the dominant `VALIDATION` class versus Run 002.
- `DOCUMENT_GENERATION`, `PRICING`, and `EXTRACTION` remain secondary and bounded in the measured sample.
- `SUPPLIER` and `BOQ_MAPPING` still did not emerge as blockers in this run.
- Run 004 therefore closes as a negative result for the Sprint 1 success gate, while still preserving the evidence that the validated baseline is stable and that the failure distribution remains concentrated in the same upstream classes.

## Validation Subtype Analysis

The six Run 004 `VALIDATION` failures break into three stable subtypes:

| Subtype | Count | Run 004 Rows | Notes |
| --- | ---: | --- | --- |
| Metadata / completeness validation | 4 | `RFQ-003-R4`, `RFQ-011-R4`, `RFQ-013-R4`, `RFQ-014-R4` | Missing closing dates, missing source/detail URLs, missing mandatory documents, and low-confidence metadata remain the dominant pattern. |
| Qualification exclusion validation | 1 | `RFQ-016-R4` | Briefing-session exclusion remains a hard non-qualifying control. |
| Technical validation gate | 1 | `RFQ-019-R4` | The technical-readiness requirement remains distinct from sourcing, pricing, and BOQ handling. |

Sprint 1.1 target:

- Harden the metadata / completeness validation path first.
- Keep qualification exclusion and technical validation as distinct reason-code families.
- Re-run against the same Run 002 baseline after the subtype-specific hardening is implemented.
