# Validation Run 008 Failure Attribution Review

## Scope

Classify the 15 `NOT_READY` records observed in the Run 008 live-queue benchmark and separate primary blockers from secondary document signals.

## Primary Attribution

| Cause | Count | Records |
| --- | ---: | --- |
| Business-rule exclusion | 6 | `FRESH_REFRESH_20260611T102258Z_70294`, `FRESH_REFRESH_20260611T101933Z_70106`, `FRESH_REFRESH_20260611T101619Z_69992`, `FRESH_REFRESH_20260611T101127Z_69711`, `Supply-and-delivery-of-banners-promotional-materials-for-anti-fraud-and-ethics-awareness`, `FRESH_REFRESH_20260609T080642Z_49749` |
| Qualification exclusion | 4 | `RFQ-XYZ`, `FIN-SCM-TEN-0236`, `FIN-SCM-TEN-0235`, `FRESH_REFRESH_20260610T180905Z_23928` |
| Expired RFQ | 4 | `FIN-SCM-TEN-0227`, `supply and delivery of new fire fighting pick-up with equipment up to 30 June 2029 11/06/2026 in 35 days`, `SUPPLY AND DELIVERY OF JOINTS ON AN AS AND WHEN REQUIRED BASIS FOR A PERIOD OF 5 YEARS AT LETHABO POWER STATION 10/06/2026 in 37 days`, `FRESH_REFRESH_20260609T091435Z_54889` |
| Missing source data | 1 | `RFQ-123` |
| Document-generation blocker | 0 | No primary READY blocker attributable to document generation on the 15-record live queue benchmark |

## Record-Level Classification

| RFQ | Primary Cause | Notes |
| --- | --- | --- |
| `RFQ-XYZ` | Qualification exclusion | Non-supply-and-delivery / incomplete source payload; too many missing fields for a recovery-based conversion |
| `FIN-SCM-TEN-0236` | Qualification exclusion | Compulsory briefing / site meeting exclusion |
| `FIN-SCM-TEN-0235` | Qualification exclusion | Compulsory briefing / site meeting exclusion |
| `FIN-SCM-TEN-0227` | Expired RFQ | Closing date already passed |
| `supply and delivery of new fire fighting pick-up with equipment up to 30 June 2029 11/06/2026 in 35 days` | Expired RFQ | Closing date already passed; document gaps remained secondary |
| `FRESH_REFRESH_20260611T102258Z_70294` | Business-rule exclusion | Below minimum profit / margin; manual pricing required |
| `FRESH_REFRESH_20260611T101933Z_70106` | Business-rule exclusion | Below minimum profit / margin; manual pricing required |
| `FRESH_REFRESH_20260611T101619Z_69992` | Business-rule exclusion | Below minimum profit / margin; manual pricing required |
| `FRESH_REFRESH_20260611T101127Z_69711` | Business-rule exclusion | Below minimum profit / margin; manual pricing required |
| `FRESH_REFRESH_20260610T180905Z_23928` | Qualification exclusion | Not supply-and-delivery |
| `SUPPLY AND DELIVERY OF JOINTS ON AN AS AND WHEN REQUIRED BASIS FOR A PERIOD OF 5 YEARS AT LETHABO POWER STATION 10/06/2026 in 37 days` | Expired RFQ | Closing date already passed; document parse incomplete was secondary |
| `FRESH_REFRESH_20260609T092352Z_55528` | Business-rule exclusion | Below minimum profit / margin; manual pricing required |
| `FRESH_REFRESH_20260609T091435Z_54889` | Expired RFQ | Closing date already passed |
| `FRESH_REFRESH_20260609T080642Z_49749` | Business-rule exclusion | Below minimum margin; manual pricing required |
| `RFQ-123` | Missing source data | Missing closing date, RFQ number, and submission method |

## Secondary Document Signals

The live queue still shows document-generation signals on a majority of the `NOT_READY` rows:

- `document_parse_incomplete`
- `missing_documents`
- `rfq_spec_document_not_detected`
- `document_confidence_below_threshold`

These signals are real, but in Run 008 they do not explain the primary readiness failure. The observed `NOT_READY` records are dominated by qualification, expiry, and business-rule exclusions.

## Conclusion

Sprint 2 improved the document-generation subsystem enough to emit quote-pack evidence on a small subset of records, but the live queue did not convert any RFQs to `READY`. The main blocker after Sprint 2 is not document generation. It is the composition of the live queue itself: expired opportunities, qualification exclusions, and business-rule exclusions dominate the remaining `NOT_READY` set.
