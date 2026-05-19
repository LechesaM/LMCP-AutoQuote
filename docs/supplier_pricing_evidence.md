# Supplier Pricing Evidence

## Purpose
This layer improves pricing defensibility, supplier traceability, and auditability without changing procurement workflow controls.

## Evidence Philosophy
- Prefer direct supplier quotes over estimates.
- Record enough context to explain where a price came from.
- Treat missing evidence as a confidence reduction, not as an automated workflow decision.
- Keep all outputs advisory only.

## Pricing Defensibility
Pricing defensibility is based on:
- supplier identity and contact details
- quote reference and receipt date
- quote validity period
- quoted items and quoted amounts
- VAT clarity
- delivery assumptions
- stock availability notes
- lead-time notes
- quotation source type

Lower-confidence sources include:
- estimated/manual pricing
- historical pricing
- phone confirmations
- catalogue-only pricing

## Pricing Confidence Scoring
The pricing confidence layer reports:
- supplier confidence score
- pricing confidence score
- logistics confidence score
- delivery confidence score
- overall pricing confidence

Confidence falls when:
- no supplier evidence exists
- pricing is estimated or manual
- delivery assumptions are missing
- VAT clarity is missing
- the quote is stale or expired
- logistics complexity is high

## Quote Aging Rules
- expired quotes are high risk
- old pricing generates warnings
- historical pricing is advisory only
- stale pricing never bypasses manual governance

## Pricing Validation Rules
Validation checks for:
- zero prices
- negative prices
- subtotal mismatches
- VAT mismatches
- delivery inconsistencies
- quantity mismatches
- unrealistic totals

Validation warnings and errors support manual review only.

## Traceability Chain
Traceability should record:
- RFQ item
- supplier source
- supplier evidence reference
- markup source
- delivery-cost assumption
- VAT treatment
- final quoted amount
- operator override notes if any

The traceability chain is append-only friendly and audit oriented.

## Operator Overrides
Operator override notes are recorded explicitly.
They do not change pricing thresholds, workflow transitions, or submission authority.

## Governance Preservation
- No autonomous final submission
- No bypass of manual approval
- No bypass of review_ready
- No bypass of proof capture
- No live supplier APIs
- No automated supplier negotiations

This layer only strengthens evidence quality for supervised operations.
