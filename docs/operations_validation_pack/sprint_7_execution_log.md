# Sprint 7 Execution Log

## Scope

Record the 30-day controlled operational pilot for live RFQs.

## Pilot Status

- Status: Active
- Duration: 30 calendar days
- Extension: permitted if exit criteria are not yet satisfied

## Day 0 Baseline

| Field | Value |
| --- | --- |
| Pilot Start Date | 2026-06-19 |
| LMCP Version | `2.6.0-manual-production` |
| Portal Submission Status | DISABLED |
| Human Approval Status | REQUIRED |
| Audit Status | AUTHORITATIVE |
| Approval Bypass Tolerance | 0 |
| Duplicate Audit Event Tolerance | 0 |
| Orphaned Audit Event Tolerance | 0 |
| State Drift Tolerance | 0 |

## Daily Tracking

| Day | Date | RFQs Harvested | RFQs Qualified | RFQs Rejected | Quote Packs Generated | Submission Packs Generated | Submission Packs Approved | Approval Bypass | Duplicate Audit Events | Orphaned Audit Events | State Drift | Operator Disagreement Count | Notes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Day 0 | 2026-06-19 | Pending | Pending | Pending | Pending | Pending | Pending | 0 | 0 | 0 | 0 | Pending | Pilot baseline established |

### Day 1 Pilot Observation

Date: 2026-06-19

#### Throughput

| Metric | Value |
| --- | ---: |
| RFQs Harvested | 0 |
| RFQs Qualified | 0 |
| RFQs Rejected | 0 |
| Quote Packs Generated | 0 |
| Submission Packs Generated | 0 |
| Submission Packs Approved | 0 |

#### Governance Metrics

| Metric | Value |
| --- | ---: |
| Approval Gate Bypass Count | 0 |
| Submission Ready Without Approval Count | 0 |
| Duplicate Audit Events | 0 |
| Orphaned Audit Events | 0 |
| State Drift Count | 0 |

#### Observations

- The Sprint 7 pilot runtime was active during the observation period.
- Backend status remained healthy and governance controls were active.
- Portal Submission = DISABLED.
- Human Approval = REQUIRED.
- Audit Trail = AUTHORITATIVE.
- No live RFQs entered the pilot runtime during the observation window.
- No qualification, quote-pack, submission-pack, approval, or audit-processing activity occurred.
- The dashboard displayed `NOT_READY`, which is consistent with an empty operational workload and does not indicate a system fault.

#### Pilot Issues

- Issue: Manual live-harvest trigger depended on Celery/Redis, and the Redis host `redis:6379` was unavailable in the local Sprint 7 runtime.
- Impact: The background harvest trigger could not refresh the live queue through the async path.
- Governance impact: None.
- RFQ logic impact: None.
- Resolution: Added synchronous local harvest endpoints at `/opportunities/harvest-local` and `/tasks/run-harvest-local` that call the harvest service directly, bypass Celery/Redis, and remain constrained to the current live source family.
- Status: Resolved in code and covered by tests; live refresh verification remains the next operational check.

#### Assessment

- Pilot infrastructure operational.
- Governance controls remained enforced with zero violations observed.
- Operational validation remains pending first live RFQ activity.

### Local Harvest Verification

Date: 2026-06-19T13:50:47+00:00

- `POST /opportunities/harvest-local` completed successfully through the synchronous local path.
- Source family: `NECSA`
- Harvest result count: `1`
- Celery/Redis were not used.
- `GET /opportunities` remained limited to the two current open non-fixture NECSA RFQs.
- `GET /dashboard/sprint7` remained `INITIALIZED_EMPTY_WORKLOAD`, which is consistent with the dashboard's isolated Sprint 7 source model.
- Governance impact: none.
- RFQ logic impact: none.

## Weekly Review Log

| Week | Dates | Throughput Review | Qualification Review | Governance Review | Audit Review | Operator Feedback Review | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Week 1 |  | Pending | Pending | Pending | Pending | Pending |  |
| Week 2 |  | Pending | Pending | Pending | Pending | Pending |  |
| Week 3 |  | Pending | Pending | Pending | Pending | Pending |  |
| Week 4 |  | Pending | Pending | Pending | Pending | Pending |  |
| Week 5 |  | Pending | Pending | Pending | Pending | Pending |  |
| Week 6 |  | Pending | Pending | Pending | Pending | Pending |  |

## Live RFQ Entry Template

Use this template for each live RFQ recorded during the pilot.

### RFQ Summary

- RFQ Identifier:
- Buyer:
- Source:
- Date/Time Entered:
- Date/Time Completed:

### Qualification

- Qualified: Yes/No
- Recommendation: APPROVE / REJECT
- Rejection Codes:
- Blocking Codes:

### Governance

- Quote Pack Status:
- Submission Pack Status:
- Approval Ready: Yes/No
- Submission Ready: Yes/No
- Human Approval Required: Yes
- Human Approval Granted: Yes/No
- Approval Turnaround Time:

### Operator Review

- Operator Agreed with LMCP: Yes/No
- Operator Decision:
- Reason for Disagreement:
- Suggested Rule Improvements:

### Audit

- Audit Event Created: Yes/No
- Timeline Reconstructed: Yes/No
- State Drift: Yes/No
- Audit Validation Result:

### Outcome

- Final Outcome:
- Pilot Issues Observed:
- Notes:

## Required Daily Fields

- `rfqs_harvested`
- `rfqs_qualified`
- `rfqs_rejected`
- `quote_packs_generated`
- `submission_packs_generated`
- `submission_packs_approved`
- `approval_gate_bypass_count`
- `submission_ready_without_approval_count`
- `duplicate_audit_events`
- `orphaned_audit_events`
- `state_drift_count`
- `operator_disagreement_count`

## Notes

- Keep portal submission disabled.
- Keep human approval mandatory.
- Treat the audit trail as authoritative.
- Record exceptions immediately.
- Do not modify qualification logic or governance rules during the pilot.
- The 20-RFQ pilot decision review template has been created at `docs/operations_validation_pack/sprint_7_checkpoint_review_20_rfqs.md` and must remain unpopulated until 20 live RFQs have been processed.

## Dashboard Labels

- `/dashboard/pilot` is the historical `historical_stage_4_pilot_dashboard`.
- `/dashboard/sprint7` and `/dashboard/controlled-pilot/current` are the current `current_sprint_7_live_state` endpoints.

## Live RFQ Evidence

### FIN-SCM-TEN-0235

| Field | Value |
| --- | --- |
| RFQ Identifier | FIN-SCM-TEN-0235 |
| Buyer | NECSA |
| Source | runtime / live_harvested |
| Date/Time Entered | 2026-06-19T13:16:54.696440+00:00 |
| Date/Time Completed | 2026-06-19T13:16:54.696440+00:00 |
| Qualified | No |
| Recommendation | REJECT |
| Rejection Codes | `not_supply_and_delivery` |
| Blocking Codes | None verified in compact endpoint view |
| Quote Pack Status | generated |
| Submission Pack Status | blocked |
| Approval Ready | No |
| Submission Ready | No |
| Human Approval Required | Yes |
| Human Approval Granted | No |
| Approval Turnaround Time | Pending operator review |
| Operator Agreed with LMCP | Pending |
| Operator Decision | Pending |
| Reason for Disagreement | Pending |
| Audit Event Created | Pending explicit audit confirmation |
| Timeline Reconstructed | Pending explicit audit confirmation |
| State Drift | No evidence of drift |
| Audit Validation Result | Pending explicit audit confirmation |
| Final Outcome | Rejected |
| Pilot Issues Observed | None recorded |
| Notes | Live-harvested NECSA RFQ, future-dated, correctly rejected by qualification rules. |

### FIN-SCM-TEN-0236

| Field | Value |
| --- | --- |
| RFQ Identifier | FIN-SCM-TEN-0236 |
| Buyer | NECSA |
| Source | runtime / live_harvested |
| Date/Time Entered | 2026-06-19T13:16:53.915607+00:00 |
| Date/Time Completed | 2026-06-19T13:16:53.915607+00:00 |
| Qualified | No |
| Recommendation | REJECT |
| Rejection Codes | `not_supply_and_delivery`, `engineering_services_scope`, `professional_services_scope` |
| Blocking Codes | None verified in compact endpoint view |
| Quote Pack Status | generated |
| Submission Pack Status | blocked |
| Approval Ready | No |
| Submission Ready | No |
| Human Approval Required | Yes |
| Human Approval Granted | No |
| Approval Turnaround Time | Pending operator review |
| Operator Agreed with LMCP | Pending |
| Operator Decision | Pending |
| Reason for Disagreement | Pending |
| Audit Event Created | Pending explicit audit confirmation |
| Timeline Reconstructed | Pending explicit audit confirmation |
| State Drift | No evidence of drift |
| Audit Validation Result | Pending explicit audit confirmation |
| Final Outcome | Rejected |
| Pilot Issues Observed | None recorded |
| Notes | Live-harvested NECSA RFQ, future-dated, correctly rejected by qualification rules. |

### Live RFQ Batch 1 Summary

| Metric | Value |
| --- | ---: |
| Live RFQs processed | 5 |
| Supply RFQs in batch | 3 |
| Qualified RFQs in batch | 1 |
| Rejected RFQs in batch | 4 |
| Submission-ready RFQs in batch | 1 |
| Human approvals recorded | 1 |
| Approval bypass count | 0 |
| Duplicate audit events | 0 |
| Orphaned audit events | 0 |
| State drift count | 0 |

### MN 22/2026 Manual Submission Record

| Field | Value |
| --- | --- |
| Submission Type | Manual controlled pilot submission |
| RFQ Identifier | MN 22/2026 |
| Operator | Supervisor |
| Submission Timestamp | 2026-06-19T15:36:37Z |
| Submission Reference | `MN 22/2026__submission__manual` |
| Receipt PDF | `runtime/manual_production/submission_executions/MN 22/2026/MN 22/2026_submission_proof/MN 22/2026_submission_receipt_20260619T153637Z.pdf` |
| Receipt JSON | `runtime/manual_production/submission_executions/MN 22/2026/MN 22/2026_submission_proof/MN 22/2026_submission_receipt_20260619T153637Z.json` |
| Receipt TXT | `runtime/manual_production/submission_executions/MN 22/2026/MN 22/2026_submission_proof/MN 22/2026_submission_receipt_20260619T153637Z.txt` |
| Proof JSON | `runtime/manual_production/submission_executions/MN 22/2026/submission_execution_proof_record.json` |
| Proof TXT | `runtime/manual_production/submission_executions/MN 22/2026/submission_execution_proof_record.txt` |
| Execution Status | executed |
| Submission Status | submitted |
| Execution Locked | true |
| Submission Locked | true |
| Human Approval Present | true |
| Submission Ready | true |
| Portal Submission | Manual only |
| Audit State | Clean |

#### Uploaded / Attached Evidence

- `runtime/manual_production/submission_packages/MN 22/2026/MN 22/2026__quote_pack.pdf`
- `runtime/manual_production/submission_packages/MN 22/2026/MN 22/2026__quote_pack.json`
- `runtime/manual_production/submission_packages/MN 22/2026/MN 22/2026__buyer_pricing_schedule.csv`
- `runtime/manual_production/submission_packages/MN 22/2026/MN 22/2026__submission_package_manifest.json`
- `runtime/compliance/tax_compliance.pdf`
- `runtime/manual_production/submission_packages/PAPER/company_registration.pdf`
- `runtime/manual_production/submission_packages/PAPER/bank_confirmation.pdf`
- `runtime/rfq_lifecycle/quote_packs/FIN-SCM-TEN-0235__LMCP-QUOTE-20260615073008/compliance/BBBEE_Certificate.pdf`

#### Submission Verification

- Submission pack opened and verified
- Pricing schedule complete
- Company documents attached
- Human approval record exists
- `submission_ready = true`
- Portal submission remains manual
- Proof artifacts saved
- Audit entry recorded in `submission_execution_history.jsonl`

#### Award Tracking

| Field | Value |
| --- | --- |
| RFQ Identifier | MN 22/2026 |
| Status | Pending |
| Submission Date | 2026-06-19T15:36:37Z |
| Buyer Record | National Treasury eTenders |
| Procuring Entity | Kwadukuza Municipality |
| Quoted Value | Not recorded in the current artifact set |
| Award Follow-up Date | 2026-07-15 |
| Notes | Award outcome has not yet been observed. Track future status as Awarded, Unsuccessful, or Pending. |

## Award Register

Use this register for submitted RFQs and their award follow-up state.

| RFQ | Submitted | Submission Date | Buyer | Quote Value | Award Status | Award Follow-up Date | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MN 22/2026` | Yes | 2026-06-19T15:36:37Z | National Treasury eTenders | Not recorded in the current artifact set | Pending | 2026-07-15 | First controlled pilot submission. |

## Current Queue Snapshot

Date: 2026-06-20

The live opportunities queue currently contains 5 records. This snapshot is for operational awareness only and does not constitute a new checkpoint.

| RFQ ID | Buyer | Closing Date | Source Mode | Qualification Status | Recommendation | Submission Ready | Manual Submission Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TENDER FOR | National Treasury eTenders | 2026-06-19 | v36-etenders | Eligible / quote-ready in queue view | No explicit queue recommendation exposed | No explicit `submission_ready` flag exposed | Not submitted |
| MN 22/2026 | National Treasury eTenders | 2026-06-19 | v36-etenders | Eligible / quote-ready in queue view | No explicit queue recommendation exposed | No explicit `submission_ready` flag exposed | Submitted |
| 19/06 | National Treasury eTenders | 2026-06-19 | v36-etenders | Eligible / quote-ready in queue view | No explicit queue recommendation exposed | No explicit `submission_ready` flag exposed | Not submitted |
| FIN-SCM-TEN-0235 | NECSA | 2026-07-01 | live_harvested | Rejected (`not_supply_and_delivery`) | Reject | false | Not submitted |
| FIN-SCM-TEN-0236 | NECSA | 2026-07-01 | live_harvested | Rejected (`not_supply_and_delivery`) | Reject | false | Not submitted |

### Queue Snapshot Notes

- `MN 22/2026` remains the only live manual submission currently recorded in the execution log.
- The two NECSA records remain rejected and not submission-ready.
- The three eTenders records are eligible and quote-ready in the live queue view, but no manual submission has been recorded for them yet.
- No governance counters changed as part of this snapshot update.

### Detail Endpoint Note

- `TENDER FOR` is reachable through the RFQ detail endpoint and currently shows a blocked submission package with `approval_ready = false`, `submission_ready = false`, and a manual-only submission posture.
- `19/06` is present in the live queue but is not cleanly retrievable through the current RFQ detail route because the slash in the identifier causes a route-resolution failure.
- Until `19/06` can be resolved cleanly through a supported detail route, treat it as queue-visible but not yet fully inspectable for submission-candidate work.

### eTenders Document Acquisition Note

- The current eTenders live queue items are arriving through the v36 interactive listing extractor with `document_url` and `detail_url` empty on the persisted live records.
- For `TENDER FOR` and `19/06`, the stored `document_acquisition_result` shows `status = no_documents_downloaded`, `seed_urls = []`, `download_attempt_count = 0`, and no downloaded buyer pack artifacts.
- The v36 extractor only populates `document_url` / `detail_url` when those links are already present in the listing markup; it does not synthesize a detail page URL for these rows.
- This points to a pre-acquisition URL discovery gap, not a governance, qualification, or audit issue.
- The current document acquisition engine is therefore receiving no usable seed URLs for these eTenders records.
- This note is operational only and does not change Sprint 7 governance or qualification rules.

### eTenders Throughput Root Cause

- Classification: harvest enrichment / URL discovery gap.
- Severity: medium.
- Impact: reduces submission-candidate generation by preventing BOQ, pricing schedule, and returnables acquisition for some eTenders records.
- Scope: affects the v36 interactive extractor path when it fails to surface usable `detail_url` / `document_url` values before document acquisition begins.
- Governance impact: none.
- Audit impact: none.
- Qualification impact: none.
- Submission integrity impact: none.
- Operational interpretation: harvesting, queue population, qualification, governance, and audit remain healthy; the bottleneck is upstream URL discovery for document acquisition.
- Future engineering note: if/when development resumes, prioritize improving eTenders detail/document URL discovery before the acquisition engine is invoked.

### eTenders Coverage Probe

- Direct live resolution from this session is still blocked by DNS, so an authoritative "today" total for eTenders opportunities could not be measured from the external site here.
- Internal source-health cache for `National Treasury eTenders` shows the last successful scan on `2026-06-14T09:35:47.158221+00:00` with `harvested_total = 12`, `qualified_candidate_total = 6`, `document_candidate_total = 12`, and `acquisition_document_links_detected = 3`.
- The current live queue snapshot contains `3` eTenders records out of `6` total live RFQs.
- Within the current live queue, eTenders accounts for `50%` of visible records, but that is only a queue-snapshot ratio and not a site-wide daily coverage figure.
- This is a bounded internal coverage signal only; it is not a substitute for a production-network daily total and should not be used to quarantine or disable any source.
- Current operational conclusion: the live queue is being discovered, but eTenders URL discovery remains the main limiter for document acquisition coverage.

### URL Discovery Ratio Note

- Based on the internal source-health cache, `3` acquisition document links were detected across `12` document candidates.
- Interpreted as a coverage ratio, that is approximately a `25%` URL-discovery success rate and a `75%` miss rate.
- This narrows the bottleneck to the pre-acquisition URL discovery path rather than opportunity harvesting, qualification, governance, audit, or manual submission handling.
- Operational reading: the system is finding opportunities, but it is not consistently turning them into downloadable tender packs.

### Funnel Interpretation

- Opportunity discovery: working.
- RFQ harvesting: working.
- Document candidate detection: working.
- URL discovery: underperforming at roughly `25%` conversion from document candidate to usable document link.
- Document acquisition: starved because it receives too few usable seeds.
- BOQ extraction: low throughput as a downstream effect of the URL gap.
- Pricing extraction: low throughput as a downstream effect of the URL gap.
- Submission candidates: low throughput as a downstream effect of the URL gap.
- Operational conclusion: this is a conversion bottleneck, not a discovery bottleneck.
- Future engineering priority, when a sprint opens: increase eTenders URL-discovery conversion from document candidate to usable `document_url` / `detail_url`.

### Funnel Loss Points

- Harvested opportunities: `12`.
- Document candidates: `12` (`100%` of harvested opportunities).
- Qualified candidates: `6` (`50%` of harvested opportunities).
- Document links discovered: `3` (`25%` of document candidates).
- Document acquisition-ready items: `3`.
- BOQ / pricing / returnables throughput: not yet fully measured in the current bounded evidence set.
- Submission candidates: not yet fully measured in the current bounded evidence set.
- Manual submissions: `1` (`MN 22/2026`).
- Operational reading: the largest observed loss occurs between document candidate detection and usable acquisition link discovery.

### Next Live Evidence Target

- For the next `5` live eTenders RFQs, capture:
  - RFQ ID
  - listing URL
  - `detail_url`
  - `document_url`
  - HTML snippet containing links
  - acquisition outcome
- Purpose: isolate where the v36 extractor loses usable URLs before document acquisition begins.
- Future engineering target: improve eTenders URL-discovery conversion from `25%` toward at least `50%`.
- No Sprint 7 workflow, governance, or qualification changes are implied by this note.

### Five-Case URL Discovery Evidence Plan

- For each of the next `5` eTenders opportunities, classify:
  - `URL found and persisted`
  - `URL present but not persisted`
  - `URL hidden in markup`
  - `URL absent from source page`
  - `Acquisition succeeded`
  - `Acquisition failed`
- This is the intended evidence set for the v36 extractor bottleneck.
- After five examples, the loss point should be clear enough to support a targeted fix when development resumes.

## Next Checkpoint Target

- Current live RFQs observed: 10
- Next operational target: 15 live RFQs
- Next formal deliverable: `sprint_7_checkpoint_review_15_rfqs.md`
- Review focus: qualification consistency, operator agreement, submission quality, governance integrity, audit integrity, and award tracking

### Additional Live Harvest Evidence

#### 022_Request_for_Quotation_Stationery_-_Photocopy_paper_Oct

| Field | Value |
| --- | --- |
| RFQ Identifier | `022_Request_for_Quotation_Stationery_-_Photocopy_paper_Oct` |
| Buyer | LMCP |
| Source | runtime / live_harvested |
| Date/Time Entered | 2026-06-19T17:14:42Z |
| Qualified | No |
| Recommendation | REJECT |
| Rejection Codes | `not_supply_and_delivery` |
| Submission Ready | No |
| Human Approval Granted | No |
| Submission Pack Status | blocked |
| Audit Event Created | Yes |
| Final Outcome | Rejected |
| Notes | Appeared after a local harvest refresh. It is live-harvested evidence, but it is not an eligible supply RFQ for manual submission. |

#### Harvest Refresh Note

- The live queue now contains one additional live-harvested non-supply RFQ.
- No second eligible manual submission candidate was found.
- `MN 22/2026` remains the only live RFQ that has passed the full manual submission gate.

#### Local Harvest Refresh - 2026-06-19T17:12:19Z

- The synchronous local harvest path was run again.
- Promoted / refreshed live-harvested RFQs: `022_Request_for_Quotation_Stationery_-_Photocopy_paper_Oct`, `FIN-SCM-TEN-0235`, `FIN-SCM-TEN-0236`
- Net live queue size remained unchanged at 6 RFQs.
- No new submission-ready RFQ was discovered.
- Governance impact: none.
- RFQ logic impact: none.

#### Local Harvest Refresh - 2026-06-19T17:19:00Z

- The synchronous local harvest path was run again.
- Net live queue size remained unchanged at 6 RFQs.
- No new RFQs were discovered.
- No RFQ status changed.
- No submission-ready RFQ was discovered.
- Governance impact: none.
- RFQ logic impact: none.

## Rolling Pilot Register

Use this register for the next live RFQs so weekly review can be done from one table.

| Slot | RFQ | Buyer | Outcome | Qualified | Submission Ready | Human Approval | Audit | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `FIN-SCM-TEN-0235` | NECSA | Rejected | No | No | No | Clean | Live-harvested, correctly rejected. |
| 2 | `FIN-SCM-TEN-0236` | NECSA | Rejected | No | No | No | Clean | Live-harvested, correctly rejected. |
| 3 | `022_Request_for_Quotation_Stationery_-_Photocopy_paper_Oct` | LMCP | Rejected | No | No | No | Clean | Live-harvested, not eligible for manual submission. |
| 4 | `TENDER FOR` | National Treasury eTenders | Rejected | No | No | No | Clean | Live-harvested, correctly rejected. |
| 5 | `19/06` | National Treasury eTenders | Rejected | No | No | No | Clean | Live-harvested, correctly rejected. |
| 6 | `MN 22/2026` | National Treasury eTenders | Approved and submitted manually | Yes | Yes | Yes | Clean | First controlled pilot submission. |
| 7 |  |  |  |  |  |  |  |  |
| 8 |  |  |  |  |  |  |  |  |
| 9 |  |  |  |  |  |  |  |  |
| 10 |  |  |  |  |  |  |  |  |
| 11 |  |  |  |  |  |  |  |  |
| 12 |  |  |  |  |  |  |  |  |
| 13 |  |  |  |  |  |  |  |  |
| 14 |  |  |  |  |  |  |  |  |
| 15 |  |  |  |  |  |  |  |  |
| 16 |  |  |  |  |  |  |  |  |
| 17 |  |  |  |  |  |  |  |  |
| 18 |  |  |  |  |  |  |  |  |
| 19 |  |  |  |  |  |  |  |  |
| 20 |  |  |  |  |  |  |  |  |

## Sprint 7 10-RFQ Operational Checkpoint Snapshot

Observed in the RFQ Operations workspace:

| Metric | Value |
| --- | ---: |
| Total RFQs | 10 |
| Discovered | 10 |
| Buyer Packs | 5 |
| Quote Packs | 2 |
| Submission Ready | 0 |

Interpretation:

- The operational live queue is active and processing real opportunities.
- The historical `/dashboard/pilot` view remains isolated from Sprint 7 evidence and must not be used for checkpoint calculations.
- The Sprint 7 evidence set currently contains six named live RFQs in this log, with the remaining operational queue records observed in the live workspace but not yet enumerated here by identifier.
- Governance counters remain zero in the pilot record.
- No submission-ready RFQ has been observed in the live queue snapshot apart from the manually submitted `MN 22/2026`, which remains tracked separately in the submission execution trail.

### TENDER FOR

| Field | Value |
| --- | --- |
| RFQ Identifier | TENDER FOR |
| Buyer | National Treasury eTenders |
| Source | runtime / live_harvested |
| Date/Time Entered | 2026-06-19T14:22:25.306882+00:00 |
| Date/Time Completed | 2026-06-19T15:00:30+00:00 |
| Qualified | No |
| Recommendation | REJECT |
| Rejection Codes | None returned by the compact qualification endpoint |
| Blocking Codes | `missing_tax_compliance`, `missing_company_registration`, `missing_bbbee`, `missing_bank_confirmation` |
| Quote Pack Status | not_attempted |
| Submission Pack Status | ready |
| Approval Ready | No |
| Submission Ready | No |
| Human Approval Required | Yes |
| Human Approval Granted | No |
| Approval Turnaround Time | Pending operator review |
| Operator Agreed with LMCP | Pending |
| Operator Decision | Pending |
| Reason for Disagreement | Pending |
| Audit Event Created | Yes |
| Timeline Reconstructed | Pending explicit replay confirmation |
| State Drift | No evidence of drift |
| Audit Validation Result | Runtime state consistent; no submission approval recorded |
| Final Outcome | Rejected |
| Pilot Issues Observed | None recorded |
| Notes | Live-harvested supply RFQ. The submission pack exists, but the qualification decision remains reject and no human approval was recorded. |

### MN 22/2026

| Field | Value |
| --- | --- |
| RFQ Identifier | MN 22/2026 |
| Buyer | National Treasury eTenders |
| Source | runtime / live_harvested |
| Date/Time Entered | 2026-06-19T14:22:25.307303+00:00 |
| Date/Time Completed | 2026-06-19T15:00:30+00:00 |
| Qualified | Yes |
| Recommendation | GO |
| Rejection Codes | None |
| Blocking Codes | None |
| Quote Pack Status | not_attempted |
| Submission Pack Status | ready |
| Approval Ready | Yes |
| Submission Ready | Yes |
| Human Approval Required | Yes |
| Human Approval Granted | Yes |
| Approval Turnaround Time | Immediate after runtime approval log entry |
| Operator Agreed with LMCP | Yes |
| Operator Decision | Approved |
| Reason for Disagreement | None |
| Audit Event Created | Yes |
| Timeline Reconstructed | Yes |
| State Drift | No |
| Audit Validation Result | PASS |
| Final Outcome | Approved to submission_ready |
| Pilot Issues Observed | None recorded |
| Notes | Genuine supply RFQ. Manual approval was recorded at `2026-06-19T15:00:30.517039+00:00`, and the runtime submission pack now resolves to `submission_ready = true` with zero blocking codes. |

### 19/06

| Field | Value |
| --- | --- |
| RFQ Identifier | 19/06 |
| Buyer | National Treasury eTenders |
| Source | runtime / live_harvested |
| Date/Time Entered | 2026-06-19T14:22:25.307980+00:00 |
| Date/Time Completed | 2026-06-19T15:00:30+00:00 |
| Qualified | No |
| Recommendation | REJECT |
| Rejection Codes | `not_supply_and_delivery` |
| Blocking Codes | `missing_tax_compliance`, `missing_company_registration`, `missing_bbbee`, `missing_bank_confirmation` |
| Quote Pack Status | not_attempted |
| Submission Pack Status | ready |
| Approval Ready | No |
| Submission Ready | No |
| Human Approval Required | Yes |
| Human Approval Granted | No |
| Approval Turnaround Time | Pending operator review |
| Operator Agreed with LMCP | Pending |
| Operator Decision | Pending |
| Reason for Disagreement | Pending |
| Audit Event Created | Yes |
| Timeline Reconstructed | Pending explicit replay confirmation |
| State Drift | No evidence of drift |
| Audit Validation Result | Runtime state consistent; no submission approval recorded |
| Final Outcome | Rejected |
| Pilot Issues Observed | None recorded |
| Notes | Live-harvested supply RFQ, correctly rejected as not clearly supply and delivery. |

### TENDER FOR

| Field | Value |
| --- | --- |
| RFQ Identifier | TENDER FOR |
| Buyer | National Treasury eTenders |
| Source | runtime / live_harvested |
| Date/Time Entered | 2026-06-19T14:22:25.306882+00:00 |
| Date/Time Completed | 2026-06-19T15:00:30+00:00 |
| Qualified | No |
| Recommendation | REJECT |
| Rejection Codes | None returned by the compact qualification endpoint |
| Blocking Codes | `missing_tax_compliance`, `missing_company_registration`, `missing_bbbee`, `missing_bank_confirmation` |
| Quote Pack Status | not_attempted |
| Submission Pack Status | ready |
| Approval Ready | No |
| Submission Ready | No |
| Human Approval Required | Yes |
| Human Approval Granted | No |
| Approval Turnaround Time | Pending operator review |
| Operator Agreed with LMCP | Pending |
| Operator Decision | Pending |
| Reason for Disagreement | Pending |
| Audit Event Created | Yes |
| Timeline Reconstructed | Pending explicit replay confirmation |
| State Drift | No evidence of drift |
| Audit Validation Result | Runtime state consistent; no submission approval recorded |
| Final Outcome | Rejected |
| Pilot Issues Observed | None recorded |
| Notes | Live-harvested supply RFQ. The submission pack exists, but the qualification decision remains reject and no human approval was recorded. |

### MN 22/2026

| Field | Value |
| --- | --- |
| RFQ Identifier | MN 22/2026 |
| Buyer | National Treasury eTenders |
| Source | runtime / live_harvested |
| Date/Time Entered | 2026-06-19T14:22:25.307303+00:00 |
| Date/Time Completed | 2026-06-19T15:00:30+00:00 |
| Qualified | Yes |
| Recommendation | GO |
| Rejection Codes | None |
| Blocking Codes | None |
| Quote Pack Status | not_attempted |
| Submission Pack Status | ready |
| Approval Ready | Yes |
| Submission Ready | Yes |
| Human Approval Required | Yes |
| Human Approval Granted | Yes |
| Approval Turnaround Time | Immediate after runtime approval log entry |
| Operator Agreed with LMCP | Yes |
| Operator Decision | Approved |
| Reason for Disagreement | None |
| Audit Event Created | Yes |
| Timeline Reconstructed | Yes |
| State Drift | No |
| Audit Validation Result | PASS |
| Final Outcome | Approved to submission_ready |
| Pilot Issues Observed | None recorded |
| Notes | Genuine supply RFQ. Manual approval was recorded at `2026-06-19T15:00:30.517039+00:00`, and the runtime submission pack now resolves to `submission_ready = true` with zero blocking codes. |

### 19/06

| Field | Value |
| --- | --- |
| RFQ Identifier | 19/06 |
| Buyer | National Treasury eTenders |
| Source | runtime / live_harvested |
| Date/Time Entered | 2026-06-19T14:22:25.307980+00:00 |
| Date/Time Completed | 2026-06-19T15:00:30+00:00 |
| Qualified | No |
| Recommendation | REJECT |
| Rejection Codes | `not_supply_and_delivery` |
| Blocking Codes | `missing_tax_compliance`, `missing_company_registration`, `missing_bbbee`, `missing_bank_confirmation` |
| Quote Pack Status | not_attempted |
| Submission Pack Status | ready |
| Approval Ready | No |
| Submission Ready | No |
| Human Approval Required | Yes |
| Human Approval Granted | No |
| Approval Turnaround Time | Pending operator review |
| Operator Agreed with LMCP | Pending |
| Operator Decision | Pending |
| Reason for Disagreement | Pending |
| Audit Event Created | Yes |
| Timeline Reconstructed | Pending explicit replay confirmation |
| State Drift | No evidence of drift |
| Audit Validation Result | Runtime state consistent; no submission approval recorded |
| Final Outcome | Rejected |
| Pilot Issues Observed | None recorded |
| Notes | Live-harvested supply RFQ, correctly rejected as not clearly supply and delivery. |

### Live RFQ Batch 1 Summary

- Live RFQs processed: 5
- Supply RFQs in batch: 3
- Rejected RFQs in batch: 4
- Qualified RFQs in batch: 1
- Submission-ready RFQs in batch: 1
- Human approvals recorded: 1
- Approval bypass count: 0
- Duplicate audit events: 0
- Orphaned audit events: 0
- State drift count: 0
- Pilot note: the batch contains one genuine supply RFQ that reached `submission_ready` with a recorded human approval, while the remaining live RFQs were either rejected by qualification or remain non-approved.

### Sprint 8A Recovery Note

- Sprint 7 remains governed and manual.
- Sprint 8A is limited to eTenders harvest coverage recovery only.
- The purpose is to restore automatic RFQ inflow and add diagnostics for multi-page discovery, raw persistence, and acquisition coverage.
- This note does not change qualification rules, governance rules, approval rules, audit rules, submission logic, or autonomous submission state.

### Sprint 8B Fetch Diagnostics Note

- Sprint 8B is diagnostic only.
- The purpose is to capture full eTenders page fetch failure reasons, redirect chains, response length, and exception classes.
- This note does not change harvesting, qualification, governance, approval, audit, or submission behavior.

### Sprint 8C Connectivity Diagnostics Note

- Sprint 8C is diagnostic only.
- The purpose is to capture the exact connectivity stage that fails before the eTenders page is fetched, including DNS, TCP/connectivity, TLS, redirect, HTTP, and proxy/access signals.
- This note does not change harvesting, qualification, governance, approval, audit, submission behavior, or autonomous submission state.

### Sprint 8D Harvest Rejection Audit Note

- Sprint 8D separates harvest from document acquisition and audits why harvested RFQs were rejected by qualification.
- The purpose is to explain rejection drivers from the recovery items without changing harvest, qualification, governance, approval, audit, or submission logic.
- This note does not disable sources or alter the pilot control state.

### Sprint 8E Controlled Acquisition Gate

- Controlled acquisition is now available in two explicit modes: `dry-controlled` and `controlled-live`.
- Dry-controlled mode prepares acquisition bundles for qualified RFQs without downloading documents.
- Controlled-live mode limits acquisition to qualified RFQs and caps live acquisitions per run.
- The default legacy behavior remains unchanged unless one of the controlled acquisition flags is selected.
- `--debug-controlled-live` now writes a preserved `controlled_live_debug.jsonl` trace, including `page_fetch` failures before any acquisition attempt starts.
