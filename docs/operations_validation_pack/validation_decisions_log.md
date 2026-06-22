# Validation Decisions Log

Capture decisions made during the operations validation period so the evidence trail stays interpretable.

## Fields

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |

## Logging Rules

- Record each decision once, as soon as it is made.
- Keep the issue statement factual and specific.
- List the options that were actually considered.
- Record the approval source or decision owner.
- Link the decision back to the active validation run.

## Example

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DEC-001 | 2026-06-18 | VALIDATION_RUN_001 | Supplier pricing unavailable for category X | Manual supplier lookup; defer RFQ; reject RFQ | Allow manual supplier lookup | Required to complete validation run | Validation Lead |

## Notes

- Use this log for exceptions, temporary process allowances, and operational clarifications.
- Do not use it for feature requests or implementation planning.
- Keep it separate from the Failure Log so decisions and defects remain distinct.

## Validation Run 001 Review

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR001-01 | 2026-06-18 | VALIDATION_RUN_001 | Why did every RFQ require exactly one manual intervention? | Mandatory governance approval; pricing review; supplier review; technical fallback; no intervention | Manual intervention was the controlled human approval gate before proof/submission | Every RFQ reached `submission_ready=true`, recorded `manual_approval_recorded=true`, and stopped before proof/submission with no technical failure evidence; the repeated intervention matches the intended supervised control path | Validation Lead |

## Review Finding

- Manual intervention was a mandatory governance approval gate, not a technical workflow failure.
- No evidence was found of a blocking supplier, pricing, extraction, or BOQ defect causing the intervention.
- The intervention was consistent across all 10 RFQs and appears intentional for the supervised path.

## Validation Run 002 Operational Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-01 | 2026-06-18 | VALIDATION_RUN_002 | Exact electrical and plumbing fixtures were not present in the current evidence inventory | Wait for a better-matched fixture set; use the closest governed hardware-style record; skip the fifth batch slot | Use the closest governed hardware-style record for the fifth batch slot | The run must continue from the available inventory without fabricating evidence or changing the frozen baseline | Validation Lead |

## Validation Run 002 RFQ-006 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-02 | 2026-06-18 | VALIDATION_RUN_002 | Below-margin fixture encountered during diversified validation | Treat as pricing review; defer until later; stop the run | Treat as a pricing-review failure and continue | The purpose of Run 002 is to measure failure distribution, not to optimize the first observed pricing defect | Validation Lead |

## Validation Run 002 RFQ-007 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-03 | 2026-06-18 | VALIDATION_RUN_002 | Ready governed fixture encountered after a pricing failure | Treat as a governance review, reject, or continue | Continue and record as a governed ready case | The run needs both ready and not-ready records to measure category diversity honestly | Validation Lead |

## Validation Run 002 RFQ-008 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-04 | 2026-06-18 | VALIDATION_RUN_002 | E2E archive fixture encountered after a run of ready records | Treat it as a duplicate, skip it, or record it | Record it as a ready governed E2E fixture | The run is measuring distribution across available evidence, and the archived E2E record is a valid data point | Validation Lead |

## Validation Run 002 RFQ-009 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-05 | 2026-06-18 | VALIDATION_RUN_002 | Ready office-consumables fixture encountered in the live/review-ready set | Skip it; treat it as duplicate; record it | Record it as a ready governed office-consumables case | The record is evidence-backed, submission-ready, and expands category coverage without changing the frozen baseline | Validation Lead |

## Validation Run 002 RFQ-010 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-06 | 2026-06-18 | VALIDATION_RUN_002 | Ready office-consumables fixture encountered in the RFQ fixture set | Skip it; treat it as duplicate; record it | Record it as a ready governed office-consumables case | The record is a high-confidence RFQ fixture and preserves the frozen baseline while completing the midpoint gate | Validation Lead |

## Validation Run 002 RFQ-011 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-07 | 2026-06-18 | VALIDATION_RUN_002 | Live cleaning-materials record rejected for missing closing date and document-confidence blockers | Treat as a pass, defer it, or record the rejection | Record it as a not-ready compliance/validation failure | The lifecycle evidence is explicit and should remain visible in the failure distribution | Validation Lead |

## Validation Run 002 RFQ-012 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-08 | 2026-06-18 | VALIDATION_RUN_002 | Ready facility-maintenance fixture selected from the archived E2E set | Skip it; reclassify it; record it | Record it as a ready governed fixture | The archived E2E evidence is high confidence and extends the stable portion of the sample without changing the baseline | Validation Lead |

## Validation Run 002 RFQ-013 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-09 | 2026-06-18 | VALIDATION_RUN_002 | Live office-supplies record rejected for missing closing date and document-processing blockers | Treat as a pass, defer it, or record the rejection | Record it as a not-ready compliance/validation failure | The lifecycle evidence is explicit and should remain visible in the failure distribution | Validation Lead |

## Validation Run 002 RFQ-014 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-10 | 2026-06-18 | VALIDATION_RUN_002 | Live office-supplies record rejected for missing source/detail URL and related document-confidence blockers | Treat as a pass, defer it, or record the rejection | Record it as a not-ready compliance/validation failure | The lifecycle evidence is explicit and should remain visible in the failure distribution | Validation Lead |

## Validation Run 002 RFQ-015 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-11 | 2026-06-18 | VALIDATION_RUN_002 | Ready store-replenishment fixture selected from the evidence inventory | Skip it; reclassify it; record it | Record it as a ready governed fixture | The record is high confidence and keeps the Run 002 sample balanced without changing the frozen baseline | Validation Lead |

## Validation Run 002 RFQ-016 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-12 | 2026-06-18 | VALIDATION_RUN_002 | Excluded briefing-session fixture selected from the evidence inventory | Skip it; reclassify it; record it | Record it as a not-ready compliance failure | The exclusion is explicit in the evidence and must remain visible in the failure distribution | Validation Lead |

## Validation Run 002 RFQ-017 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-13 | 2026-06-18 | VALIDATION_RUN_002 | Incomplete schedule detail blocked readiness on an eligible supply-and-delivery fixture | Treat as ready, defer it, or record the blocker | Record it as a document-generation failure | The incomplete schedule is a distinct document-quality issue and should remain visible separately from compliance exclusions | Validation Lead |

## Validation Run 003 RFQ-004 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR003-01 | 2026-06-18 | VALIDATION_RUN_003 | Fixed delivery sample RFQ-004-R2 needed an explicit proof and audit trace on the governed RFQ_005 root | Leave the sample as a readiness-only record; use a fallback intake record; execute the fixed RFQ_005 delivery chain | Execute the fixed RFQ_005 delivery chain and record proof plus a central audit event | Run 003 is delivery validation and must stay aligned to the selected fixed sample, not a fallback intake | Validation Lead |

## Validation Run 003 RFQ-005 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR003-02 | 2026-06-18 | VALIDATION_RUN_003 | Fixed delivery sample RFQ-005-R2 needed the same approval-review-proof chain on the governed RFQ_004 root | Leave it as readiness-only; use a fallback intake record; execute the fixed RFQ_004 delivery chain | Execute the fixed RFQ_004 delivery chain and record proof plus a central audit event | Run 003 needs repeatable delivery evidence on each fixed sample in the selected set | Validation Lead |

## Validation Run 003 RFQ-007 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR003-03 | 2026-06-18 | VALIDATION_RUN_003 | Fixed delivery sample RFQ-007-R2 needed to remain aligned with the archived governed REAL-PILOT-002 evidence chain | Skip the archived fixture; force a fresh approval; use the fixed archived proof chain | Use the archived governed proof chain and record the matching central audit event | The selected sample is a proof-recorded governed fixture, so the validation objective is to retain and verify delivery evidence rather than regenerate it | Validation Lead |

## Validation Run 003 RFQ-008 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR003-04 | 2026-06-18 | VALIDATION_RUN_003 | Fixed delivery sample RFQ-008-R2 needed to remain aligned with the archived governed REAL-PILOT-003-E2E-20260528 evidence chain | Skip the archived fixture; force a fresh approval; use the fixed archived proof chain | Use the archived governed proof chain and record the matching central audit event | The selected sample is a proof-recorded governed fixture, so the validation objective is to retain and verify delivery evidence rather than regenerate it | Validation Lead |

## Validation Run 003 RFQ-009 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR003-05 | 2026-06-18 | VALIDATION_RUN_003 | Fixed delivery sample RFQ-009-R2 needed to remain aligned with the live/review-ready REAL-PILOT-001 evidence chain | Skip the live fixture; force a new approval; use the existing live/review-ready proof chain | Use the existing live/review-ready proof chain and record the matching central audit event | The selected sample is already review-ready and traceable, so the validation objective is to preserve and verify delivery evidence rather than regenerate it | Validation Lead |

## Validation Run 003 RFQ-010 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR003-06 | 2026-06-18 | VALIDATION_RUN_003 | Fixed delivery sample RFQ-010-R2 needed to remain aligned with the live/review-ready RFQ-VALID-001 evidence chain | Skip the live fixture; force a new approval; use the existing live/review-ready proof chain | Use the existing live/review-ready proof chain and record the matching central audit event | The selected sample is already review-ready and traceable, so the validation objective is to preserve and verify delivery evidence rather than regenerate it | Validation Lead |

## Validation Run 003 Sample Integrity Adjustment

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR003-07 | 2026-06-18 | VALIDATION_RUN_003 | Two original fixed sample IDs did not map to local ready delivery artifacts in the evidence inventory | Keep the original placeholder IDs; fabricate evidence; replace the unmatched sample slots with archive-backed ready fixtures | Replace the unmatched sample slots with archive-backed ready fixtures only | Sample integrity matters more than preserving placeholder IDs; the run must remain executable and auditable against evidence that already exists | Validation Lead |

## Validation Run 003 Archive-Backed Delivery Evidence

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR003-08 | 2026-06-18 | VALIDATION_RUN_003 | Archive-backed Run 003 fixture RFQ-012-R2 needed its delivery proof and audit trace recorded against the REAL-PILOT-002-E2E-20260528 evidence chain | Leave it unrecorded; substitute a placeholder; record the archive-backed evidence chain | Record the archive-backed evidence chain and central audit event | The selected archive-backed fixture is executable and evidence-backed, so Run 003 should preserve the trace instead of inventing a new one | Validation Lead |
| VR003-09 | 2026-06-18 | VALIDATION_RUN_003 | Archive-backed Run 003 fixture RFQ-015-R2 needed its delivery proof and audit trace recorded against the REAL-PILOT-001-E2E-20260528 evidence chain | Leave it unrecorded; substitute a placeholder; record the archive-backed evidence chain | Record the archive-backed evidence chain and central audit event | The selected archive-backed fixture is executable and evidence-backed, so Run 003 should preserve the trace instead of inventing a new one | Validation Lead |
| VR003-10 | 2026-06-18 | VALIDATION_RUN_003 | Archive-backed Run 003 fixture RFQ-018-R2 needed its delivery proof and audit trace recorded against the RFQ-VALID-001-E2E-20260528 evidence chain | Leave it unrecorded; substitute a placeholder; record the archive-backed evidence chain | Record the archive-backed evidence chain and central audit event | The selected archive-backed fixture is executable and evidence-backed, so Run 003 should preserve the trace instead of inventing a new one | Validation Lead |
| VR003-11 | 2026-06-18 | VALIDATION_RUN_003 | Archive-backed Run 003 fixture RFQ-020-R2 needed its delivery proof and audit trace recorded against the PILOT-005-E2E-20260528 evidence chain | Leave it unrecorded; substitute a placeholder; record the archive-backed evidence chain | Record the archive-backed evidence chain and central audit event | The selected archive-backed fixture is executable and evidence-backed, so Run 003 should preserve the trace instead of inventing a new one | Validation Lead |

## Validation Run 003 Closeout

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR003-12 | 2026-06-18 | VALIDATION_RUN_003 | Close out the fixed delivery sample after the remaining archive-backed fixtures were executed and traced successfully | Leave the run open; rerun the sample; mark it complete | Mark the run complete and preserve the audit/proof trail | The fixed Run 003 sample now has 10/10 successful deliveries, 10/10 proof records, and 10/10 audit references with no delivery failures | Validation Lead |

## Validation Run 004 Initiation

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR004-01 | 2026-06-18 | VALIDATION_RUN_004 | Start the post-Sprint 1 measurement gate against the frozen Run 002 baseline | Delay the run; open a new planning cycle; begin measurement | Begin Validation Run 004 immediately and measure against the Run 002 baseline | Sprint 1 is implemented and the next useful step is evidence, not more planning | Validation Lead |

## Validation Run 004 First Review

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR004-02 | 2026-06-18 | VALIDATION_RUN_004 | First five evidence-backed records need an auditable midpoint comparison | Hold the run until the full 20 RFQs are complete; publish the first review slice; revise the baseline interpretation now | Publish the first review slice and continue the remaining Run 004 sample | The first slice is already comparable to the Run 002 first-review pattern and shows a 3 READY / 2 NOT READY split without pricing or document-generation regression | Validation Lead |

## Validation Run 004 Closeout

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR004-03 | 2026-06-18 | VALIDATION_RUN_004 | Full Run 004 sample completed; compare the measured failure distribution against the Run 002 baseline and close the gate | Keep the run open; reinterpret the sample; move directly to Sprint 2 | Close Run 004 and record the final comparison against Run 002 | The full measured sample did not reduce `VALIDATION` failures below the Sprint 1 target, while `DOCUMENT_GENERATION`, `PRICING`, and `EXTRACTION` remained bounded and `SUPPLIER` / `BOQ_MAPPING` stayed absent | Validation Lead |

## Validation Run 004 Subtype Analysis

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR004-04 | 2026-06-18 | VALIDATION_RUN_004 | Six Run 004 validation failures need to be separated into actionable subtypes before Sprint 1.1 | Treat all validation failures as one bucket; start Sprint 2 immediately; split by observed subtype and target the dominant subtype first | Split the failures into metadata/completeness, qualification exclusion, and technical-validation subtypes, then target metadata/completeness in Sprint 1.1 | The evidence shows that the dominant surviving class is metadata/completeness validation, not supplier, BOQ, or delivery | Validation Lead |

## Validation Run 005 Initiation

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR005-01 | 2026-06-18 | VALIDATION_RUN_005 | Open the post-Sprint 1.1 re-measurement gate against the same diversified baseline sample | Start Sprint 2 immediately; delay measurement; open Run 005 and compare against Run 004 | Open Validation Run 005 against the Run 004 comparison sample | Sprint 1.1 is implemented and the next useful step is measurement, not more design | Validation Lead |

## Validation Run 005 First Review

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR005-02 | 2026-06-18 | VALIDATION_RUN_005 | First five evidence-backed Run 005 rows need an auditable comparison against the Run 004 first-review slice | Hold the run until the full 20 RFQs are complete; publish the first review slice; re-open Sprint 1.1 | Publish the first review slice and continue the remaining Run 005 sample | The first slice is comparable to the Run 004 first-review pattern and still shows metadata-completeness blockers in the failing rows, so the full sample is still needed | Validation Lead |

## Validation Run 005 Midpoint

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR005-03 | 2026-06-18 | VALIDATION_RUN_005 | The 10/20 checkpoint does not yet show a reduction in metadata-completeness failures | Stop early and declare Sprint 1.1 ineffective; pivot to Sprint 2; continue the full measurement run | Continue Run 005 to RFQ-020-R5 | The second five-row slice is entirely not-ready and still dominated by metadata-completeness blockers, so the full sample is still required before changing remediation priority | Validation Lead |

## Validation Run 005 Closeout

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR005-04 | 2026-06-18 | VALIDATION_RUN_005 | Full Run 005 sample completed against the frozen Sprint 1.1 baseline | Declare Sprint 1.1 successful; pivot immediately to Sprint 2; reopen Sprint 1.2 | Close Run 005 and keep validation/completeness as the active remediation target | The full sample closed with `2 READY / 18 NOT READY` and the dominant metadata-completeness blocker did not materially decrease versus Run 004, so Sprint 1.1 is not proven | Validation Lead |

## Validation Run 002 RFQ-018 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-14 | 2026-06-18 | VALIDATION_RUN_002 | Below-margin pricing blocked readiness on an eligible supply-and-delivery fixture | Treat as ready, defer it, or record the blocker | Record it as a pricing failure | The margin gate is a distinct business-rule failure and should remain separate from compliance and document issues | Validation Lead |

## Validation Run 002 RFQ-019 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-15 | 2026-06-18 | VALIDATION_RUN_002 | Technical validation requirement keeps a high-confidence fixture out of the current readiness set | Treat as ready, defer it, or record the blocker | Record it as a validation failure | The record is evidence-backed but not ready for the current stage because technical validation remains a gating requirement | Validation Lead |

## Validation Run 002 RFQ-020 Note

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR002-16 | 2026-06-18 | VALIDATION_RUN_002 | Final qualified household-products fixture selected to close the sample | Skip it; defer it; record it | Record it as a ready governed fixture | The record is a high-confidence final data point and closes Run 002 without changing the frozen baseline | Validation Lead |

## Validation Run 006 Initiation

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR006-01 | 2026-06-18 | VALIDATION_RUN_006 | Open the post-Sprint 1.2 re-measurement gate against the same diversified baseline sample | Start Sprint 2 immediately; delay measurement; open Run 006 and compare against Run 005 | Open Validation Run 006 against the Run 005 comparison sample | Sprint 1.2 is implemented and the next useful step is measurement, not more design | Validation Lead |

## Validation Run 006 Midpoint

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR006-02 | 2026-06-18 | VALIDATION_RUN_006 | The first 10 executable live-queue records do not yet show a metadata-completeness reduction below the Run 005 baseline | Stop at midpoint; pivot to Sprint 2; continue to the full 20-RFQ sample | Continue Run 006 to RFQ-020-R6 | The midpoint evidence still shows metadata-completeness blockers, but the run must close before any remediation decision is made | Validation Lead |

## Validation Run 006 Sample Integrity

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR006-03 | 2026-06-18 | VALIDATION_RUN_006 | The live evidence store currently exposes only 15 executable RFQs, leaving 5 planned Run 006 slots unmaterialized | Fabricate the missing records; reassign the planned sample; mark the run complete anyway | Keep Run 006 open and record the sample-integrity shortfall | The run cannot be closed against the planned 20-RFQ sample without inventing evidence | Validation Lead |

## Validation Run 006 Closeout

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR006-04 | 2026-06-18 | VALIDATION_RUN_006 | Resolve the sample-integrity shortfall and close the run | Fabricate the missing records; keep the run open; retire the missing records and re-baseline to the live queue | Retire the missing five RFQs, re-baseline Run 006 as a 15-RFQ live queue benchmark, and close the run | The missing records are not recoverable from the current evidence store without invention, so the honest closeout is to freeze the live queue benchmark and preserve evidence integrity | Validation Lead |

## Validation Run 006 Remediation Decision

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR006-05 | 2026-06-18 | VALIDATION_RUN_006 | Decide whether to move to document-generation hardening or continue targeting metadata recovery | Start Sprint 2; start Sprint 1.3; reopen Run 006 | Approve Sprint 1.3 - Metadata Recovery Hardening and defer Sprint 2 | The closeout evidence shows metadata completeness remains the largest independent blocker and likely upstream of extraction and document-generation gaps | Validation Lead |

## Validation Run 007 Initiation

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR007-01 | 2026-06-18 | VALIDATION_RUN_007 | Open the post-Sprint 1.3 live-queue measurement gate | Start Sprint 2; change scoring; continue analysis only; open Run 007 | Open Validation Run 007 against the live-queue benchmark | Sprint 1.3 is implemented and the next useful step is measurement, not more planning | Validation Lead |

## Validation Run 007 Closeout

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR007-02 | 2026-06-18 | VALIDATION_RUN_007 | The live queue benchmark produced READY conversions after Sprint 1.3 | Keep the run open; pivot to Sprint 2; revisit metadata recovery | Close Run 007 and preserve the live-queue benchmark as the post-Sprint 1.3 evidence set | The live queue produced 2 READY outcomes and therefore demonstrates that recovery now changes readiness outcomes, even though metadata-completeness remains dominant | Validation Lead |

## Validation Run 007 Conversion Analysis

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR007-03 | 2026-06-18 | VALIDATION_RUN_007 | Determine whether Sprint 1.4 has a business case after the Run 007 conversion analysis | Approve Sprint 1.4; defer Sprint 1.4 and start Sprint 2; reopen Run 007 | Defer Sprint 1.4 and do not start it yet | The conversion analysis shows only 2 clear READY conversions and the remaining failures are dominated by expired opportunities, qualification exclusions, business-rule blockers, and genuinely missing source data | Validation Lead |

## Sprint 2 Planning Approval

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR007-04 | 2026-06-18 | SPRINT_2_PLAN | Approve Sprint 2 planning after the Run 007 conversion analysis | Keep deferring Sprint 2; reopen metadata recovery; approve document-generation planning | Approve Sprint 2 planning and create the document-generation hardening plan | The live queue now has measurable READY conversions from metadata recovery, and the remaining recoverable surface area is better assigned to document-generation hardening | Validation Lead |

## Sprint 2 Implementation

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR008-01 | 2026-06-18 | SPRINT_2_IMPL | Implement Sprint 2 before opening Run 008 | Keep Sprint 2 in planning only; defer implementation; implement the approved document-generation workstreams | Implement Sprint 2 and open the Run 008 measurement gate next | The approved Sprint 2 workstreams are now implemented in the document-quality path, while supplier coverage, BOQ mapping, delivery, audit, and metadata recovery remain frozen unless a regression appears | Validation Lead |

## Validation Run 008 Closeout

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR008-02 | 2026-06-18 | VALIDATION_RUN_008 | Close the post-Sprint 2 live-queue measurement gate | Keep the run open; pivot immediately to another sprint; record the observed live-queue benchmark as complete | Close Run 008 and preserve the live-queue benchmark as the Sprint 2 evidence set | The live queue produced 0 READY outcomes, three records generated quote-pack evidence but remained not-ready, and no delivery or audit regressions were observed; Sprint 2 is therefore partially effective but does not yet meet the readiness success gate | Validation Lead |

## Validation Run 008 Failure Attribution

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR008-03 | 2026-06-18 | VALIDATION_RUN_008 | Determine why all 15 live-queue records remained NOT_READY after Sprint 2 | Start another sprint; attribute all failures to document generation; classify the records by primary blocker and record the attribution only | Record the Run 008 failure attribution review and defer any new sprint decision | The live queue is dominated by business-rule, qualification, expiry, and missing-source-data blockers, while document-generation gaps are secondary signals rather than the primary reason READY did not increase | Validation Lead |

## Sprint 5 Simulation Gate

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR008-04 | 2026-06-19 | SPRINT_5_SIMULATION_GATE | Approve the final Sprint 5 simulation run as the gate into Sprint 6 audit stress testing | Keep tuning the lane model; rerun the 100-RFQ simulation; approve the gate and move to Sprint 6 | Approve the gate and move to Sprint 6 audit stress testing | The final Sprint 5 run at `runtime/simulation_runs/sprint5-20260619T003649Z/` preserves Lane A/B/C behavior, routes the non-qualified non-rejected population into `lane_d_not_recommended`, leaves `lane_e_edge_cases` at 0, and shows zero approval-gate or audit-integrity regressions | Validation Lead |

## Sprint 7 Pilot Authorization

| Decision ID | Date | Validation Run | Issue | Options Considered | Decision Taken | Reason | Approved By |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VR009-01 | 2026-06-19 | SPRINT_7_CONTROLLED_OPERATIONAL_PILOT | Authorize the controlled operational pilot after Sprint 6 passed | Keep the system in simulation-only mode; expand feature scope; authorize Sprint 7 under frozen controls | Authorize Sprint 7 as a controlled operational pilot with frozen governance controls | Sprint 6 proved audit authority, timeline reconstruction, and zero-bypass behavior under 100/250/500 RFQ load, so the next value is live operational evidence rather than new development | Validation Lead |
