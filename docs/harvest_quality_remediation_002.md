# HARVEST-QUALITY-REMEDIATION-002

## Scope

This review stays in Operational Hold State and investigates harvest-quality data completeness only.

It covers:

- closing-date extraction review
- source/detail URL traceability review

It does not change:

- qualification thresholds
- profit thresholds
- supervised-live governance
- Track A
- Track B
- Regression Run #2
- Tier 25

## Evidence Basis

- Current live RFQ ledger: [runtime/rfq_lifecycle/rfqs.json](/Users/cash/Documents/runtime/rfq_lifecycle/rfqs.json)
- Rejection frequency review: [docs/harvest_rejection_analysis_001.md](/Users/cash/Documents/docs/harvest_rejection_analysis_001.md)

## Current Rejection Pattern

| Rejection Reason | Count |
| --- | ---: |
| `missing_closing_date` | 2 |
| `below_minimum_profit` | 1 |
| `missing_source_or_detail_url` | 1 |

## Workstream A: Closing-Date Extraction Review

### Evidence

- `RFQ-12345` -> `closing_date = null`
- `RFQ-67890` -> `closing_date = null`

### Current Interpretation

- The live ledger records no closing date for both entries.
- The current evidence does not yet prove whether the missing dates were absent from the source material or lost during normalization.
- The blocker is operationally important because closing-date absence prevents deadline verification and submission-window calculation.

### Questions To Answer Next

- Are closing dates present on the source pages but absent from the runtime ledger?
- Are they present in PDFs or attached documents but not extracted?
- Are they embedded in tables, images, or linked documents that the current parser does not capture?

## Workstream B: Source URL Traceability Review

### Evidence

- `RFQ-123` -> `source_url = null`, `detail_url = null`, `document_url = null`

### Current Interpretation

- The ledger currently lacks source and detail URLs for the blocked RFQ.
- That weakens traceability, re-acquisition, and audit evidence.
- The evidence is sufficient to classify this as a traceability gap, but not yet sufficient to pinpoint whether the gap originated at the source feed, the normalizer, or the capture layer.

### Questions To Answer Next

- Did the source feed provide URLs and they were dropped later?
- Did the source page omit the URLs entirely?
- Is the normalization layer intentionally suppressing weak or generic URLs?

## Decision Guidance

- If closing dates are present in source artifacts but missing in runtime, prioritize closing-date capture remediation.
- If source URLs are present in source artifacts but missing in runtime, prioritize traceability normalization.
- If either field is genuinely absent in the source, the remediation target should shift to source-health reporting and not qualification rules.
- `below_minimum_profit` should remain unchanged unless later evidence shows false negatives.

## Governance Impact

- None.
- No submission rules changed.
- No qualification rules changed.
- No supervised-live controls changed.

## Outcome

- Status: `EVIDENCE REVIEW COMPLETE`
- Recommendation: `Proceed with source-artifact inspection before any parser or threshold change`
