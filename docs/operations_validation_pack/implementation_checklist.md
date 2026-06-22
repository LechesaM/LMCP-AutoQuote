# LMCP Implementation Checklist

Execution tracker for the post-validation engineering cycle.

## Purpose

Track sprint ownership, task status, acceptance criteria, and validation metrics directly against the engineering roadmap.

## Status Legend

- `NOT STARTED`
- `IN PROGRESS`
- `BLOCKED`
- `DONE`

## Sprint 1 - Validation and Compliance Hardening

Objective:

Reduce the dominant Run 002 failure class.

Tasks:

| Task | Status | Owner | Acceptance Criteria | Validation Metric |
| --- | --- | --- | --- | --- |
| Closing date validator | DONE | TBD | Missing or invalid closing dates are flagged before readiness | Validation failures reduced by >= 50% vs Run 002 |
| Source URL validator | DONE | TBD | Missing or invalid source URLs are flagged before readiness | Validation failures reduced by >= 50% vs Run 002 |
| RFQ number validator | DONE | TBD | RFQ identifiers are present and normalized before readiness | Validation failures reduced by >= 50% vs Run 002 |
| Confidence scoring framework | DONE | TBD | Low-confidence extractions are escalated to review required | Validation failures reduced by >= 50% vs Run 002 |
| Qualification rule engine | DONE | TBD | Briefing exclusions, category exclusions, profit margin, and supply-only rules are applied consistently | Validation failures reduced by >= 50% vs Run 002 |
| Compliance readiness scoring | DONE | TBD | READY, REVIEW REQUIRED, and NOT READY are produced with reason codes | Validation failures reduced by >= 50% vs Run 002 |

Sprint 1 acceptance criteria:

- Validation failures reduced by at least 50% against the Run 002 baseline.
- Validation Run 004 has been measured; the target was not met in the full sample.

## Sprint 1.1 - Validation Subtype Hardening

Objective:

Target the surviving validation/completeness subtype from Run 004.

Tasks:

| Task | Status | Owner | Acceptance Criteria | Validation Metric |
| --- | --- | --- | --- | --- |
| Metadata completeness hardening | DONE | TBD | Missing closing dates, missing source/detail URLs, missing mandatory documents, and low-confidence metadata are surfaced as distinct reason codes before readiness | Validation failures reduced to <= 3 vs Run 002 |
| Qualification exclusion separation | DONE | TBD | Briefing-session and other exclusion rules remain separate from metadata completeness | Validation failures reduced to <= 3 vs Run 002 |
| Technical validation gate separation | DONE | TBD | Technical-readiness requirements remain isolated from sourcing and pricing gates | Validation failures reduced to <= 3 vs Run 002 |

Sprint 1.1 acceptance criteria:

- Validation failures reduced to `<= 3` against the Run 002 baseline.
- Validation subtype reason codes remain distinct and auditable.
- No new document-generation, pricing, extraction, delivery, or audit regressions are introduced.

Sprint 1.1 status:

- Implemented
- Re-measurement gate opened in `Validation Run 005`

## Sprint 1.2 - Metadata Recovery Hardening

Objective:

Convert metadata completeness from a hard stop into a recoverable condition where evidence is available.

Tasks:

| Task | Status | Owner | Acceptance Criteria | Validation Metric |
| --- | --- | --- | --- | --- |
| Closing-date recovery | DONE | TBD | Secondary extraction or fallback discovery can recover closing dates before a hard stop | Metadata completeness failures reduced vs Run 005 |
| Source URL recovery | DONE | TBD | Alternate source discovery can recover source/detail URLs before a hard stop | Metadata completeness failures reduced vs Run 005 |
| Mandatory document inventory | DONE | TBD | Missing mandatory documents are detected, classified, and escalated for recovery | Metadata completeness failures reduced vs Run 005 |
| Confidence enrichment | DONE | TBD | Multi-source reconciliation and provenance improve metadata confidence before NOT_READY | Metadata completeness failures reduced vs Run 005 |

Sprint 1.2 acceptance criteria:

- Metadata / Completeness failures reduce relative to the Run 005 baseline.
- Recovery paths remain auditable and reason-coded.
- No new delivery, audit-trace, supplier, pricing, or BOQ regressions are introduced.

Sprint 1.2 status:

- Implemented
- Re-measurement gate opened in `Validation Run 006`

## Sprint 1.3 - Metadata Recovery Hardening

Objective:

Reduce the live-queue metadata-completeness blocker by improving recovery of missing or low-confidence procurement metadata.

Tasks:

| Task | Status | Owner | Acceptance Criteria | Validation Metric |
| --- | --- | --- | --- | --- |
| Closing-date recovery | NOT STARTED | TBD | Primary extraction, secondary extraction, and schedule scans can recover closing dates before a hard stop | Metadata completeness failures reduced versus Run 006 |
| Source / detail URL recovery | NOT STARTED | TBD | Alternate source discovery and provenance storage recover source/detail URLs before a hard stop | Metadata completeness failures reduced versus Run 006 |
| Mandatory document recovery | NOT STARTED | TBD | Document inventory, attachment reconciliation, and annexure detection recover missing required documents where evidence exists | Metadata completeness failures reduced versus Run 006 |
| Confidence escalation | NOT STARTED | TBD | Cross-checking and enrichment raise metadata confidence before NOT_READY is emitted | Metadata completeness failures reduced versus Run 006 |

Sprint 1.3 acceptance criteria:

- Metadata / Completeness failures reduce relative to the Run 006 live-queue benchmark.
- Recovery paths remain auditable and reason-coded.
- No new delivery, audit-trace, supplier, pricing, or BOQ regressions are introduced.

Sprint 1.3 status:

- Implemented
- Re-measurement gate opened in `Validation Run 007`
- Validation Run 007 will be the next measurement gate

## Sprint 2 - Document Generation Hardening

Objective:

Reduce document-generation-caused NOT_READY outcomes for otherwise eligible opportunities.

Planning status:

- Implemented
- Execution gate will be `Validation Run 008`

Tasks:

| Task | Status | Owner | Acceptance Criteria | Validation Metric |
| --- | --- | --- | --- | --- |
| Pricing schedule completeness | DONE | TBD | Pricing schedules are generated whenever source data permits and completeness is reason-coded | Document generation failures reduced to near zero |
| Returnables completeness | DONE | TBD | Returnables are extracted, packaged, and reported consistently | Document generation failures reduced to near zero |
| Annexure handling | DONE | TBD | Annexures are detected, tracked, and surfaced explicitly | Document generation failures reduced to near zero |
| Submission-pack completeness | DONE | TBD | Required pack components are validated before READY is emitted | Document generation failures reduced to near zero |
| Mandatory attachment validation | DONE | TBD | Required attachments are tracked individually and missing items are reason-coded | Document generation failures reduced to near zero |
| Document quality scoring | DONE | TBD | A document quality score is exposed and used in readiness reporting | Document generation failures reduced to near zero |
| Governance rule | DONE | TBD | Governance remains explicit and frozen while document generation is hardened | No regressions in delivery or audit layers |

Sprint 2 acceptance criteria:

- Document-generation failures reduced to near zero.
- READY count maintained or improved against the Run 007 live benchmark.
- No delivery regressions and no audit regressions are introduced.

## Sprint 3 - Extraction Hardening

Objective:

Improve RFQ extraction robustness across varied structures.

Tasks:

| Task | Status | Owner | Acceptance Criteria | Validation Metric |
| --- | --- | --- | --- | --- |
| Multi-pass extraction | NOT STARTED | TBD | Field detection, validation, and confidence scoring are staged explicitly | Extraction failures reduced to near zero |
| Confidence threshold handling | NOT STARTED | TBD | Low-confidence extraction results become REVIEW REQUIRED instead of silent acceptance | Extraction failures reduced to near zero |
| Extraction audit trail | NOT STARTED | TBD | Extracted value, source location, confidence score, and validation result are retained | Extraction failures reduced to near zero |
| Structure variability tests | NOT STARTED | TBD | RFQ structure variance is exercised and recorded against the same baseline | Extraction failures reduced to near zero |

Sprint 3 acceptance criteria:

- Extraction failures reduced to near zero.

## Validation Gate

After Sprint 3:

- Run Validation Run 004
- Compare against the Run 002 baseline

| Failure Class | Run 002 Baseline | Run 004 Target |
| --- | ---: | ---: |
| VALIDATION | 6 | <= 3 |
| DOCUMENT_GENERATION | 2 | 0-1 |
| EXTRACTION | 1 | 0 |
| PRICING | Business rule | No change |

Exit criteria:

- Validation failures materially reduced
- Document-generation failures materially reduced
- Extraction failures materially reduced
- Delivery success remains >= 95%
- Audit traceability remains 100%

## Notes

- This checklist is the execution control for the remediation cycle.
- Sprint ownership should be assigned before marking any task `IN PROGRESS`.
- Acceptance criteria are derived directly from the completed validation programme.
