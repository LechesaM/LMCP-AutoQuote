# RFQ Master Tracker

Single source of truth for Week 1 operations validation.

## Fields

| RFQ_ID | Tender Number | Department | Province | Category | Publication Date | Closing Date | Estimated Value | Qualified (Y/N) | Supplier Found (Y/N) | Pricing Complete (Y/N) | BOQ Complete (Y/N) | Submission Pack Ready (Y/N) | Submitted (Y/N) | Awarded (Y/N) | Failure Category | Notes |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RFQ-001 | FRESH-IMPORT-20260608231020-96429 | Unknown | Unknown | Supply and delivery | Unknown | Unknown | R150,000 | Y | Y | Y | Y | Y | N | N | NONE | Submission-ready on existing pipeline; manual approval recorded; no proof submission performed. |
| RFQ-002 | FRESH-IMPORT-20260608231023-96452 | Unknown | Unknown | Supply and delivery | Unknown | Unknown | R150,000 | Y | Y | Y | Y | Y | N | N | NONE | Submission-ready on existing pipeline; manual interventions: 1; manual approval recorded; no proof submission performed. |
| RFQ-003 | FRESH-IMPORT-20260608231111-96513 | Unknown | Unknown | Supply and delivery | Unknown | Unknown | R150,000 | Y | Y | Y | Y | Y | N | N | NONE | Submission-ready on existing pipeline; manual interventions: 1; manual approval recorded; no proof submission performed. |
| RFQ-004 | FRESH-IMPORT-20260608231122-96538 | Unknown | Unknown | Supply and delivery | Unknown | Unknown | R150,000 | Y | Y | Y | Y | Y | N | N | NONE | Submission-ready on existing pipeline; manual interventions: 1; manual approval recorded; no proof submission performed. |
| RFQ-005 | FRESH-IMPORT-20260608231214-96661 | Unknown | Unknown | Supply and delivery | Unknown | Unknown | R150,000 | Y | Y | Y | Y | Y | N | N | NONE | Submission-ready on existing pipeline; manual interventions: 1; manual approval recorded; no proof submission performed. |
| RFQ-006 | FRESH-IMPORT-20260608231219-96688 | Unknown | Unknown | Supply and delivery | Unknown | Unknown | R150,000 | Y | Y | Y | Y | Y | N | N | NONE | Submission-ready on existing pipeline; manual interventions: 1; manual approval recorded; no proof submission performed. |
| RFQ-007 | FRESH-IMPORT-20260608231307-96732 | Unknown | Unknown | Supply and delivery | Unknown | Unknown | R150,000 | Y | Y | Y | Y | Y | N | N | NONE | Submission-ready on existing pipeline; manual interventions: 1; manual approval recorded; no proof submission performed. |
| RFQ-008 | FRESH-IMPORT-20260608231426-96881 | Unknown | Unknown | Supply and delivery | Unknown | Unknown | R150,000 | Y | Y | Y | Y | Y | N | N | NONE | Submission-ready on existing pipeline; manual interventions: 1; manual approval recorded; no proof submission performed. |
| RFQ-009 | FRESH-IMPORT-20260608231505-96939 | Unknown | Unknown | Supply and delivery | Unknown | Unknown | R150,000 | Y | Y | Y | Y | Y | N | N | NONE | Submission-ready on existing pipeline; manual interventions: 1; manual approval recorded; no proof submission performed. |
| RFQ-010 | FRESH_INTAKE_20260608T213935Z_98763 | Unknown | Unknown | Supply and delivery | Unknown | Unknown | R150,000 | Y | Y | Y | Y | Y | Y | N | NONE | Submission-ready on existing pipeline; manual interventions: 1; manual approval recorded; proof submission and central audit trace recorded in Run 003. |

## Current Run Status

- RFQ-001 executed through the current supervised pipeline path.
- Submission readiness was achieved.
- No blocking failures were recorded for this RFQ.
- RFQ-002 executed through the current supervised pipeline path.
- Submission readiness was achieved.
- No blocking failures were recorded for this RFQ.
- RFQ-003 executed through the current supervised pipeline path.
- Submission readiness was achieved.
- No blocking failures were recorded for this RFQ.
- RFQ-004 executed through the current supervised pipeline path.
- Submission readiness was achieved.
- No blocking failures were recorded for this RFQ.
- RFQ-005 executed through the current supervised pipeline path.
- Submission readiness was achieved.
- No blocking failures were recorded for this RFQ.
- RFQ-006 executed through the current supervised pipeline path.
- Submission readiness was achieved.
- No blocking failures were recorded for this RFQ.
- RFQ-007 executed through the current supervised pipeline path.
- Submission readiness was achieved.
- No blocking failures were recorded for this RFQ.
- RFQ-008 executed through the current supervised pipeline path.
- Submission readiness was achieved.
- No blocking failures were recorded for this RFQ.
- RFQ-009 executed through the current supervised pipeline path.
- Submission readiness was achieved.
- No blocking failures were recorded for this RFQ.
- RFQ-010 executed through the current supervised pipeline path.
- Submission readiness was achieved.
- Proof submission and central audit trace were recorded for this RFQ.
- No blocking failures were recorded for this RFQ.

## Validation Run 002 First Diversified Batch

| RFQ_ID | Tender Number | Category | Department | Province | Qualified (Y/N) | Supplier Found (Y/N) | Pricing Complete (Y/N) | BOQ Complete (Y/N) | Submission Pack Ready (Y/N) | Submitted (Y/N) | Awarded (Y/N) | Failure Category | Reason_For_Manual_Approval | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RFQ-001-R2 | RFQ-MESSY-001 | Office Supplies | Unknown | Gauteng | Y | N | N | N | N | N | N | EXTRACTION | GOVERNANCE_REVIEW | High-evidence fixture; eligible; expected submission-ready false; zero line items and no buyer name. |
| RFQ-002-R2 | RFQ-MISSING-001 | Cleaning Materials | District Example | Eastern Cape | Y | Y | Y | Y | N | N | N | DOCUMENT_GENERATION | GOVERNANCE_REVIEW | High-evidence fixture; eligible; expected submission-ready false; source document is missing from the fixture path. |
| RFQ-003-R2 | PILOT-005-E2E-20260528 | PPE | Department of Environmental Affairs | Western Cape | N | Y | Y | N | N | N | N | VALIDATION | GOVERNANCE_REVIEW | Protective clothing; missing closing date and mandatory documents; recommendation reject. |
| RFQ-004-R2 | RFQ_005 | Building Materials | Thulamela Local Municipality | Limpopo | Y | Y | Y | Y | Y | Y | N | NONE | GOVERNANCE_REVIEW | Run 003 delivery sample; manual approval, review, proof, and central audit trace recorded. |
| RFQ-005-R2 | RFQ_004 | General Hardware | South African Forestry Company SOC Ltd (SAFCOL) | Mpumalanga | Y | Y | Y | Y | Y | Y | N | NONE | GOVERNANCE_REVIEW | Run 003 delivery sample; manual approval, review, proof, and central audit trace recorded. |
| RFQ-006-R2 | REAL-PILOT-005 | Supply and delivery | Municipal Records Unit | Mpumalanga | Y | Y | N | Y | N | N | N | PRICING | PRICING_REVIEW | Eligible below-margin fixture; manual pricing review recorded; minimum profit and minimum supply margin are not met. |
| RFQ-007-R2 | REAL-PILOT-002 | Supply and delivery | District Services Office | Western Cape | Y | Y | Y | Y | Y | Y | N | NONE | GOVERNANCE_REVIEW | Run 003 delivery sample; archived proof evidence and central audit trace recorded. |
| RFQ-008-R2 | REAL-PILOT-003-E2E-20260528 | Supply and delivery | Regional Stores Division | KwaZulu-Natal | Y | Y | Y | Y | Y | Y | N | NONE | GOVERNANCE_REVIEW | Run 003 delivery sample; archived proof evidence and central audit trace recorded. |
| RFQ-009-R2 | REAL-PILOT-001 | Office Supplies | Metro Procurement Unit | Gauteng | Y | Y | Y | Y | Y | Y | N | NONE | GOVERNANCE_REVIEW | Run 003 delivery sample; live/review-ready proof evidence and central audit trace recorded. |
| RFQ-010-R2 | RFQ-VALID-001 | Office Consumables | City of Example | Gauteng | Y | Y | Y | Y | Y | N | N | NONE | GOVERNANCE_REVIEW | Ready office-consumables fixture from the RFQ fixture set; submission-ready and evidence-backed. |
| RFQ-011-R2 | RFQ-67890 | Cleaning Materials | Smoke Fixture eTenders | Unknown | Y | N | N | N | N | N | N | VALIDATION | COMPLIANCE_REVIEW | Live cleaning-materials record; rejected in the lifecycle for missing closing date and related document-confidence blockers. |
| RFQ-012-R2 | REAL-PILOT-002-E2E-20260528 | Facility Maintenance Supplies | District Services Office | Western Cape | Y | Y | Y | Y | Y | N | N | NONE | GOVERNANCE_REVIEW | Ready governed facility-maintenance record from the archived E2E set; stable baseline evidence with no new blocker class. |
| RFQ-013-R2 | RFQ-12345 | Office Supplies | Smoke Fixture eTenders | Unknown | Y | N | N | N | N | N | N | VALIDATION | COMPLIANCE_REVIEW | Live office-supplies record; rejected in the lifecycle for missing closing date and document-processing blockers. |
| RFQ-014-R2 | RFQ-123 | Office Supplies | Metro Procurement Unit | Unknown | Y | N | N | N | N | N | N | VALIDATION | COMPLIANCE_REVIEW | Live office-supplies record; rejected in the lifecycle for missing source/detail URL, closing-date, and document-confidence blockers. |
| RFQ-015-R2 | REAL-PILOT-001-E2E-20260528 | Office Supplies | Metro Procurement Unit | Gauteng | Y | Y | Y | Y | Y | N | N | NONE | GOVERNANCE_REVIEW | Archive-backed ready fixture with proof and central audit evidence. |
| RFQ-016-R2 | RFQ-AMBIG-001 | General | City of Example | Western Cape | N | N | N | N | N | N | N | VALIDATION | COMPLIANCE_REVIEW | Excluded briefing-session fixture; blocked as a general/non-qualifying opportunity with no submission-ready state. |
| RFQ-017-R2 | RFQ-INCOMPLETE-SCHEDULE-001 | Supply and Delivery | Municipality Example | KwaZulu-Natal | Y | Y | Y | Y | N | N | N | DOCUMENT_GENERATION | GOVERNANCE_REVIEW | Eligible supply-and-delivery fixture with incomplete schedule detail; expected submission-ready false in the fixture evidence. |
| RFQ-018-R2 | RFQ-VALID-001-E2E-20260528 | Office Consumables | City of Example | Gauteng | Y | Y | Y | Y | Y | N | N | NONE | GOVERNANCE_REVIEW | Archive-backed ready fixture with proof and central audit evidence. |
| RFQ-019-R2 | RFQ_001 | Equipment Supply | Air Traffic and Navigation Services (ATNS) | Gauteng | Y | Y | Y | Y | Y | N | N | VALIDATION | COMPLIANCE_REVIEW | High-confidence technical-validation fixture; ready after qualification but explicitly requires technical validation before award. |
| RFQ-020-R2 | PILOT-005-E2E-20260528 | Protective Clothing | Department of Environmental Affairs | Western Cape | Y | Y | Y | Y | Y | N | N | NONE | GOVERNANCE_REVIEW | Archive-backed ready fixture with proof and central audit evidence. |

## Validation Run 002 Review Gate

- Run 002 evidence is being accumulated under the frozen baseline.
- Manual approval reason is captured on every recorded row so far.
- The first review point remains useful, but the run should continue through RFQ-020 under the same rules.

## Validation Run 003 Delivery Evidence

| RFQ_ID | Tender Number | Category | Department | Province | Qualified (Y/N) | Supplier Found (Y/N) | Pricing Complete (Y/N) | BOQ Complete (Y/N) | Submission Pack Ready (Y/N) | Submitted (Y/N) | Awarded (Y/N) | Failure Category | Reason_For_Manual_Approval | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RFQ-012-R2 | REAL-PILOT-002-E2E-20260528 | Facility Maintenance Supplies | District Services Office | Western Cape | Y | Y | Y | Y | Y | Y | N | NONE | GOVERNANCE_REVIEW | Archive-backed delivery evidence chain retained for the adjusted Run 003 sample; proof and central audit trace recorded. |
| RFQ-015-R2 | REAL-PILOT-001-E2E-20260528 | Office Supplies | Metro Procurement Unit | Gauteng | Y | Y | Y | Y | Y | Y | N | NONE | GOVERNANCE_REVIEW | Archive-backed delivery evidence chain retained for the adjusted Run 003 sample; proof and central audit trace recorded. |
| RFQ-018-R2 | RFQ-VALID-001-E2E-20260528 | Office Consumables | City of Example | Gauteng | Y | Y | Y | Y | Y | Y | N | NONE | GOVERNANCE_REVIEW | Archive-backed delivery evidence chain retained for the adjusted Run 003 sample; proof and central audit trace recorded. |
| RFQ-020-R2 | PILOT-005-E2E-20260528 | Protective Clothing | Department of Environmental Affairs | Western Cape | Y | Y | Y | Y | Y | Y | N | NONE | GOVERNANCE_REVIEW | Archive-backed delivery evidence chain retained for the adjusted Run 003 sample; proof and central audit trace recorded. |

## Validation Run 004 Summary

- Run 004 measured the Sprint 1 hardened baseline against the Run 002 category-diversity sample.
- Final evidence-backed distribution: `11 READY / 9 NOT READY`.
- Final failure distribution: `VALIDATION 6`, `DOCUMENT_GENERATION 1`, `PRICING 1`, `EXTRACTION 1`, `SUPPLIER 0`, `BOQ_MAPPING 0`.
- Sprint 1 did not materially reduce the dominant `VALIDATION` class versus Run 002.

## Validation Run 005 Midpoint Note

- Run 005 reached the 10/20 checkpoint against the frozen Sprint 1.1 baseline.
- Cumulative first-10 evidence-backed result: `2 READY / 8 NOT READY`.
- The second five-row slice remains not-ready across all rows, with metadata-completeness blockers still visible.
- The run continues to the full 20 RFQs before any remediation decision is made.

## Validation Run 005 Closeout

- Run 005 closed across the full 20-RFQ sample against the frozen Sprint 1.1 baseline.
- Final result: `2 READY / 18 NOT READY`.
- Metadata-completeness remained the dominant blocker; qualification-exclusion and technical-validation cases were still present but did not change the overall conclusion.
- Sprint 1.1 improved observability and subtype reporting but did not materially move the readiness distribution below the Run 004 target.

## Validation Run 006 Midpoint

The first 10 executable live-queue records currently available in `runtime/live_rfqs.json` were measured as the Run 006 midpoint evidence set.

| RFQ_ID | Buyer RFQ Number | Title | Quote Ready | Primary Readiness Gaps | Notes |
| --- | --- | --- | --- | --- | --- |
| RFQ-001-R6 | RFQ-XYZ | Manual quantity verification RFQ | N | `missing_source_or_detail_url`, `not_supply_and_delivery`, `below_minimum_profit`, `below_minimum_margin`, `missing_closing_date`, `missing_submission_method`, `document_confidence_below_threshold`, `missing_document_confidence`, `missing_documents`, `document_parse_incomplete`, `rfq_spec_document_not_detected`, `manual_pricing_required`, `sbd_or_returnables_manual_required` | Metadata completeness and document parsing remain blocked |
| RFQ-002-R6 | FIN-SCM-TEN-0236 | Professional engineering services upgrade | N | `not_supply_and_delivery`, `compulsory_briefing_or_site_meeting_detected` | Qualification exclusion |
| RFQ-003-R6 | FIN-SCM-TEN-0235 | Grade C to Grade B facility upgrade | N | `not_supply_and_delivery`, `compulsory_briefing_or_site_meeting_detected` | Qualification exclusion |
| RFQ-004-R6 | FIN-SCM-TEN-0227 | Contract Advisory Service for 3 years | N | `not_supply_and_delivery`, `closing_date_passed` | Qualification exclusion with closing-date issue |
| RFQ-005-R6 | supply and delivery of new fire fighting pick-up with equipment up to 30 June 2029 11/06/2026 in 35 days | supply and delivery of new fire fighting pick-up with equipment up to 30 June 2029 11/06/2026 in 35 days | N | `closing_date_passed`, `document_confidence_below_threshold`, `missing_document_confidence`, `missing_documents`, `document_parse_incomplete`, `rfq_spec_document_not_detected`, `sbd_or_returnables_manual_required` | Metadata completeness and document parsing remain blocked |
| RFQ-006-R6 | FRESH_REFRESH_20260611T102258Z_70294 | supply and delivery of new fire fighting pick-up with equipment up to 30 June 2029 11/06/2026 in 35 days | N | `below_minimum_profit`, `below_minimum_margin`, `closing_date_passed`, `profit_below_threshold`, `document_confidence_below_threshold`, `missing_document_confidence`, `missing_documents`, `document_parse_incomplete`, `rfq_spec_document_not_detected`, `manual_pricing_required`, `sbd_or_returnables_manual_required` | Pricing and metadata remain blocked |
| RFQ-007-R6 | FRESH_REFRESH_20260611T101933Z_70106 | supply and delivery of new fire fighting pick-up with equipment up to 30 June 2029 11/06/2026 in 35 days | N | `below_minimum_profit`, `below_minimum_margin`, `closing_date_passed`, `profit_below_threshold`, `document_confidence_below_threshold`, `missing_document_confidence`, `missing_documents`, `document_parse_incomplete`, `rfq_spec_document_not_detected`, `manual_pricing_required`, `sbd_or_returnables_manual_required` | Pricing and metadata remain blocked |
| RFQ-008-R6 | FRESH_REFRESH_20260611T101619Z_69992 | supply and delivery of new fire fighting pick-up with equipment up to 30 June 2029 11/06/2026 in 35 days | N | `below_minimum_profit`, `below_minimum_margin`, `closing_date_passed`, `profit_below_threshold`, `document_confidence_below_threshold`, `missing_document_confidence`, `missing_documents`, `document_parse_incomplete`, `rfq_spec_document_not_detected`, `manual_pricing_required`, `sbd_or_returnables_manual_required` | Pricing and metadata remain blocked |
| RFQ-009-R6 | FRESH_REFRESH_20260611T101127Z_69711 | supply and delivery of new fire fighting pick-up with equipment up to 30 June 2029 11/06/2026 in 35 days | N | `below_minimum_profit`, `below_minimum_margin`, `closing_date_passed`, `profit_below_threshold`, `document_confidence_below_threshold`, `missing_document_confidence`, `missing_documents`, `document_parse_incomplete`, `rfq_spec_document_not_detected`, `manual_pricing_required`, `sbd_or_returnables_manual_required` | Pricing and metadata remain blocked |
| RFQ-010-R6 | FRESH_REFRESH_20260610T180905Z_23928 | Repair and installation of machinery and equipment | N | `not_supply_and_delivery`, `below_minimum_margin`, `closing_date_passed`, `document_confidence_below_threshold`, `missing_document_confidence`, `missing_documents`, `document_parse_incomplete`, `rfq_spec_document_not_detected`, `manual_pricing_required`, `sbd_or_returnables_manual_required` | Qualification exclusion plus metadata/document gaps |

## Validation Run 006 Sample Integrity Note

- The live evidence store currently exposes `15` executable RFQs for Run 006, not the full planned `20`.
- The remaining `5` planned Run 006 slots are not present in the evidence store, so the run cannot be closed without fabricating records.
- Run 006 remains open until the missing evidence is surfaced or the control sample is formally retired.

## Validation Run 007 Completion

The same live queue benchmark was re-measured after Sprint 1.3 metadata recovery hardening.

| RFQ_ID | Buyer RFQ Number | Title | Readiness | Recovered Closing Date | Recovered Source URL | Recovered Detail URL | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LIVE-001-R7 | RFQ-XYZ | Manual quantity verification RFQ | NOT_READY |  |  |  | Not enough recoverable metadata to convert to READY |
| LIVE-002-R7 | FIN-SCM-TEN-0236 | Professional engineering services upgrade | READY | `01 July 2026` | `https://www.necsa.co.za/` | `https://www.necsa.co.za/wp-content/uploads/2026/05/FIN-SCM-TEN-0236.zip` | Sprint 1.3 converted the record to READY |
| LIVE-003-R7 | FIN-SCM-TEN-0235 | Grade C to Grade B facility upgrade | READY | `01 July 2026` | `https://www.necsa.co.za/` | `https://www.necsa.co.za/wp-content/uploads/2026/05/FIN-SCM-TEN-0235.zip` | Sprint 1.3 converted the record to READY |
| LIVE-004-R7 | FIN-SCM-TEN-0227 | Contract Advisory Service for 3 years | NOT_READY | `17 June 2026` | `https://www.necsa.co.za/` | `https://www.necsa.co.za/wp-content/uploads/2026/05/FIN-SCM-TEN-0227.zip` | Recovered metadata present, but closing date is already passed |
| LIVE-005-R7 | supply and delivery of new fire fighting pick-up with equipment up to 30 June 2029 11/06/2026 in 35 days | same title | NOT_READY | `2026-06-11` | `https://www.etenders.gov.za/` | `file:///Users/cash/Documents/runtime/rfq_zip_content_extraction/reports/supply-and-delivery-of-new-fire-fighting-pick-up-with-equipment-up-to-30-June-2029-11-06-2026-in-35__zip_content_extraction_report.json` | Recovered metadata present, but closing date is already passed |
| LIVE-006-R7 | FRESH_REFRESH_20260611T102258Z_70294 | same title | NOT_READY | `2026-06-11` | `https://www.etenders.gov.za/Home/opportunities` | `https://www.etenders.gov.za/Home/opportunities` | Recovered metadata present, but pricing and closing-date issues remain |
| LIVE-007-R7 | FRESH_REFRESH_20260611T101933Z_70106 | same title | NOT_READY | `2026-06-11` | `https://www.etenders.gov.za/Home/opportunities` | `https://www.etenders.gov.za/Home/opportunities` | Recovered metadata present, but pricing and closing-date issues remain |
| LIVE-008-R7 | FRESH_REFRESH_20260611T101619Z_69992 | same title | NOT_READY | `2026-06-11` | `https://www.etenders.gov.za/Home/opportunities` | `https://www.etenders.gov.za/Home/opportunities` | Recovered metadata present, but pricing and closing-date issues remain |
| LIVE-009-R7 | FRESH_REFRESH_20260611T101127Z_69711 | same title | NOT_READY | `2026-06-11` | `https://www.etenders.gov.za/Home/opportunities` | `https://www.etenders.gov.za/Home/opportunities` | Recovered metadata present, but pricing and closing-date issues remain |
| LIVE-010-R7 | FRESH_REFRESH_20260610T180905Z_23928 | Repair and installation of machinery and equipment | NOT_READY | `2026-06-10` | `https://www.etenders.gov.za/Home/opportunities` | `https://www.etenders.gov.za/Home/opportunities` | Not supply and delivery; recovered metadata did not change qualification |
| LIVE-011-R7 | SUPPLY AND DELIVERY OF JOINTS ON AN AS AND WHEN REQUIRED BASIS FOR A PERIOD OF 5 YEARS AT LETHABO POWER STATION 10/06/2026 in 37 days | same title | NOT_READY | `2026-06-10` | `https://www.etenders.gov.za/Home/opportunities` | `file:///Users/cash/Documents/runtime/rfq_zip_content_extraction/reports/SUPPLY-AND-DELIVERY-OF-JOINTS-ON-AN-AS-AND-WHEN-REQUIRED-BASIS-FOR-A-PERIOD-OF-5-YEARS-AT-LETHABO-PO__zip_content_extraction_report.json` | Recovered metadata present, but closing date is already passed |
| LIVE-012-R7 | FRESH_REFRESH_20260609T092352Z_55528 | SUPPLY AND DELIVERY OF BANNERS/PROMOTIONAL MATERIALS FOR ANTI-FRAUD AND ETHICS AWARENESS 09/06/2026 in 10 days | NOT_READY | `2026-06-09` | `https://www.etenders.gov.za/Home/opportunities` | `https://www.etenders.gov.za/Home/opportunities` | Recovered metadata present, but pricing and closing-date issues remain |
| LIVE-013-R7 | FRESH_REFRESH_20260609T091435Z_54889 | Supplies: General | NOT_READY | `2026-06-09` | `https://www.etenders.gov.za/Home/opportunities` | `https://www.etenders.gov.za/Home/opportunities` | Recovered metadata present, but closing date is already passed |
| LIVE-014-R7 | FRESH_REFRESH_20260609T080642Z_49749 | GIVEAWAY MATERIALS | NOT_READY | `2026-06-09` | `https://www.etenders.gov.za/Home/opportunities` | `https://www.etenders.gov.za/Home/opportunities` | Recovered metadata present, but pricing and closing-date issues remain |
| LIVE-015-R7 | RFQ-123 | RFQ-123 | NOT_READY |  |  |  | Insufficient recoverable metadata in the live queue benchmark |

## Validation Run 008 Live Queue Benchmark

- Run 008 measured the same 15-record live queue after Sprint 2 document-generation hardening.
- `READY = 0`, `NOT_READY = 15`.
- Three records now show `quote_pack_generated = true` with `pricing_schedule_status = detected`, `returnables_status = detected`, and `boq_status = detected`.
- The generated quote-pack records were `FIN-SCM-TEN-0236`, `FIN-SCM-TEN-0235`, and `FIN-SCM-TEN-0227`.
- These records still remained `NOT_READY` because of qualification or expiry blockers, so Sprint 2 did not produce a READY conversion on the live queue.

## Usage Rules

- One line per RFQ.
- Update status as the RFQ moves through the pipeline.
- Record failure category immediately when a stage stops.
- Keep notes short and factual.
- Use this sheet as the operational source of truth for Day 1 through Day 30.
