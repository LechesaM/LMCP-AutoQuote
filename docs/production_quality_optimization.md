# Production Quality Optimization

## Purpose

This branch improves production-quality outcomes without changing workflow governance, procurement rules, or submission controls.

## RFQ Extraction Scoring

- RFQ extraction is scored for required-field completeness.
- Missing buyer, missing closing date, missing line items, and ambiguous category generate warnings.
- Exclusion detection adds confidence for:
  - medical consumables
  - IT equipment
  - petrol
  - diesel
  - catering
  - compulsory briefing sessions

## Buyer Schedule Completion Scoring

- Buyer pricing schedules are checked for:
  - item description
  - quantity
  - unit
  - unit price
  - total
  - VAT where applicable
  - delivery where applicable
- Incomplete rows generate warnings and reduce completion score.

## Quote-Pack Readiness Scoring

- Quote packs are scored for professional completeness.
- Checks include:
  - company details
  - buyer details
  - tender reference
  - pricing schedule
  - VAT treatment
  - validity period
  - delivery terms
  - signature/approval placeholder
- Readiness also expects:
  - consistent artifact naming
  - generated PDF, JSON, and manifest artifacts where applicable
- Missing artifacts lower readiness and are reported as warnings.
- Missing-field warnings are emitted with stable codes:
  - `missing_company_details`
  - `missing_buyer_details`
  - `missing_tender_reference`
  - `missing_pricing_schedule`
  - `missing_vat_treatment`
  - `missing_validity_period`
  - `missing_delivery_terms`
  - `missing_signature_placeholder`
  - `missing_artifacts`
  - `inconsistent_artifact_naming`

## Supplier Pricing Confidence

- Supplier quotes are scored for confidence and anomaly risk.
- Checks include:
  - zero price
  - negative price
  - unusually low price
  - unusually high price
  - missing delivery cost
  - missing VAT clarity
- Comparison summaries remain advisory only.

## Supplier Pricing Evidence

- Supplier pricing evidence captures:
  - supplier name and contact
  - quote reference and receipt date
  - validity period
  - quoted items and quoted amounts
  - delivery assumptions
  - VAT clarity
  - stock and lead-time notes
  - quotation source type
- Evidence completeness and pricing defensibility are reported for operator awareness.
- Stale or expired quotes are flagged as advisory risk signals only.
- Traceability summaries are append-only friendly and remain advisory only.

## Operator Recommendations

- Operator recommendations are advisory only.
- Allowed recommendations include:
  - approve
  - review
  - capture proof
  - refuse
  - archive
  - rerun validation
- Recommendations must not mutate workflow state.

## RFQ Qualification Engine

- RFQ qualification is advisory and gating only.
- Qualification may recommend:
  - GO
  - MANUAL_REVIEW
  - REJECT
- Qualification does not enable autonomous final submission.
- Qualification does not bypass manual approval, review-ready, or proof-capture requirements.
- Qualification summaries may be shown on the dashboard and monitoring reports for operator awareness.

## Tender Success Analytics

- Real tender outcomes are tracked manually.
- Analytics report:
  - RFQs processed
  - RFQs eligible
  - RFQs refused
  - quotes generated
  - reviewed packs
  - proof captured
  - submitted manually
  - won / lost / unknown / cancelled / expired
- Awards are never inferred automatically.

## Rules

- All recommendations are advisory only.
- No autonomous final submission.
- No bypass of manual approval, review-ready, or proof-capture requirements.
