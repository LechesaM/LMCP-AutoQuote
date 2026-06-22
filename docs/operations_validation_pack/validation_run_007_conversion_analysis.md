# Validation Run 007 Conversion Analysis

## Scope

Analyze the 15-record live-queue benchmark after Sprint 1.3 and determine whether the remaining NOT_READY records are realistically recoverable.

## Group A - Converted

| RFQ | Missing Fields Before Recovery | Recovery Actions Triggered | Recovered Closing Date | Recovered Source URL | Recovered Document Signals | Final Readiness | Why It Became READY |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FIN-SCM-TEN-0236 | Closing-date evidence, source/detail provenance, submission method, and document-confidence evidence were not directly exposed in the queue payload | Secondary provenance scan, URL normalization, closing-date extraction, confidence enrichment | Yes | Yes | Yes | READY | The live queue provided enough provenance for Sprint 1.3 to reconstruct the key metadata and remove the last blockers |
| FIN-SCM-TEN-0235 | Closing-date evidence, source/detail provenance, submission method, and document-confidence evidence were not directly exposed in the queue payload | Secondary provenance scan, URL normalization, closing-date extraction, confidence enrichment | Yes | Yes | Yes | READY | The live queue provided enough provenance for Sprint 1.3 to reconstruct the key metadata and remove the last blockers |

## Group B - Not Converted

| RFQ | Remaining Missing / Blocking Fields | Recovery Actions Attempted | Recovery Actions Successful | Recovery Actions Unsuccessful | Qualification Exclusion Present | Truly Unrecoverable |
| --- | --- | --- | --- | --- | --- | --- |
| RFQ-XYZ | Closing date, source URL, detail URL, submission method, document confidence, documents, parse completeness | None materially recoverable from the payload | No | Yes | Yes | Yes |
| FIN-SCM-TEN-0227 | Closing date already passed | Provenance recovery | Metadata recovered, but the opportunity is expired | Closing-date recovery cannot override the expired closing date | Yes | Yes |
| supply and delivery of new fire fighting pick-up with equipment up to 30 June 2029 11/06/2026 in 35 days | Closing date already passed, document parse incomplete, missing documents, RFQ spec not detected | Provenance recovery, document signal detection | Metadata recovered | The record is still expired and non-ready | No | Yes |
| FRESH_REFRESH_20260611T102258Z_70294 | Below minimum profit, below minimum margin, closing date already passed, pricing/manual pricing required, document parse incomplete | Provenance recovery, document signal detection | Metadata recovered | The business-rule blockers remain and the opportunity is expired | No | Yes |
| FRESH_REFRESH_20260611T101933Z_70106 | Below minimum profit, below minimum margin, closing date already passed, pricing/manual pricing required, document parse incomplete | Provenance recovery, document signal detection | Metadata recovered | The business-rule blockers remain and the opportunity is expired | No | Yes |
| FRESH_REFRESH_20260611T101619Z_69992 | Below minimum profit, below minimum margin, closing date already passed, pricing/manual pricing required, document parse incomplete | Provenance recovery, document signal detection | Metadata recovered | The business-rule blockers remain and the opportunity is expired | No | Yes |
| FRESH_REFRESH_20260611T101127Z_69711 | Below minimum profit, below minimum margin, closing date already passed, pricing/manual pricing required, document parse incomplete | Provenance recovery, document signal detection | Metadata recovered | The business-rule blockers remain and the opportunity is expired | No | Yes |
| FRESH_REFRESH_20260610T180905Z_23928 | Not supply and delivery, below minimum margin, closing date already passed, manual pricing required | Provenance recovery, pricing signal detection | Metadata recovered | The record remains a non-qualifying opportunity | Yes | Yes |
| SUPPLY AND DELIVERY OF JOINTS ON AN AS AND WHEN REQUIRED BASIS FOR A PERIOD OF 5 YEARS AT LETHABO POWER STATION 10/06/2026 in 37 days | Closing date already passed, document parse incomplete, missing documents, RFQ spec not detected | Provenance recovery, document signal detection | Metadata recovered | The opportunity is expired | No | Yes |
| FRESH_REFRESH_20260609T092352Z_55528 | Below minimum profit, below minimum margin, closing date already passed, pricing/manual pricing required, document parse incomplete | Provenance recovery, pricing signal detection | Metadata recovered | The business-rule blockers remain and the opportunity is expired | No | Yes |
| FRESH_REFRESH_20260609T091435Z_54889 | Closing date already passed, document parse incomplete, missing documents | Provenance recovery, document signal detection | Metadata recovered | The opportunity is expired | No | Yes |
| FRESH_REFRESH_20260609T080642Z_49749 | Below minimum margin, closing date already passed, pricing/manual pricing required, document parse incomplete | Provenance recovery, pricing signal detection | Metadata recovered | The opportunity is expired and price-constrained | No | Yes |
| RFQ-123 | Missing closing date, missing RFQ number, missing submission method, not supply and delivery | No meaningful recovery path | No | Yes | Yes | Yes |

## Distribution

| Failure Cause | Count | Notes |
| --- | ---: | --- |
| Recoverable closing-date gap | 2 | The only clear READY conversions came from records whose missing/indirect closing-date evidence was recoverable |
| Recoverable URL gap | 2 | The same two converted records had source/detail provenance recovered successfully |
| Recoverable document gap | 13 | Document signals were recovered across most of the benchmark, but they did not overcome expiry or business-rule blockers |
| Qualification exclusion | 5 | Non-supply-and-delivery / explicit exclusion cases remain a hard stop |
| Unrecoverable source data | 2 | The two clearly unrecoverable records lacked enough source evidence to support recovery |

## Decision

Sprint 1.4 is not justified yet.

## Reason

- Only 2 of 15 records converted to READY.
- The remaining 13 records are dominated by expired opportunities, qualification exclusions, business-rule blockers, or genuinely missing source data.
- Another metadata-recovery sprint is unlikely to convert another 3-5 RFQs from this benchmark.

## Recommendation

Defer Sprint 1.4 and move to Sprint 2 planning once the team is ready to accept that the live queue contains a large number of non-recoverable or expired opportunities.
