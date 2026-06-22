# Validation Run 006 Midpoint Report

## Scope

The midpoint evidence set is the first 10 executable records currently present in `runtime/live_rfqs.json`.

## Summary

| KPI | Run 005 Baseline | Run 006 Midpoint |
| --- | ---: | ---: |
| READY | 2 | 0 |
| NOT READY | 18 | 10 |
| Metadata / Completeness | 18 | 7 |
| Qualification Exclusion | 6 | 5 |
| Technical Validation Gate | 1 | 0 |
| Document Generation | 0 | 7 |
| Extraction | 0 | 7 |

## Evidence Notes

- `document_confidence_below_threshold`: 7
- `missing_document_confidence`: 7
- `missing_documents`: 7
- `document_parse_incomplete`: 7
- `rfq_spec_document_not_detected`: 7
- `sbd_or_returnables_manual_required`: 7
- `closing_date_passed`: 7
- `below_minimum_margin`: 6
- `manual_pricing_required`: 6
- `not_supply_and_delivery`: 5
- `below_minimum_profit`: 5
- `profit_below_threshold`: 4
- `compulsory_briefing_or_site_meeting_detected`: 2
- `missing_source_or_detail_url`: 1
- `missing_closing_date`: 1
- `missing_submission_method`: 1

## Conclusion

Sprint 1.2 improved metadata recovery instrumentation and reason-code fidelity, but the live-queue benchmark does not yet show a reduction in metadata-completeness failures below the Run 005 baseline.

## Sample Integrity Decision

The live evidence store currently exposes `15` executable records for Run 006. The planned `20`-RFQ sample was not fully materialized, so the run has been re-baselined as a `15-RFQ Live Queue Benchmark` and closed on the evidence that exists.

## Closeout Comparison

| Failure Class | Run 005 | Run 006 |
| --- | ---: | ---: |
| Metadata / Completeness | 18 | 11 |
| Qualification Exclusion | 6 | 6 |
| Technical Validation Gate | 1 | 0 |
| Document Generation | 0 | 10 |
| Extraction | 0 | 10 |
| READY | 2 | 0 |
| Sample Type | Curated | Live Queue |
