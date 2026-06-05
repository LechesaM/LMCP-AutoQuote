# Consistency Review

- Generated at: 2026-06-05T14:52:14.178204+00:00
- RFQ Gold Dataset scenarios: 247
- Supplier Intelligence records: 294
- Pricing Intelligence lines: 500
- Tender-Win Intelligence records: 217

## Validation Results
- JSON index validated: True
- YAML index validated: True
- Placeholder scan passed: True
- Evidence-path check passed: True

## Metric Promotion Rule
- Pack-local metrics are not automatically promoted to dashboard metrics.
- Promotion requires a separate evidence review before any dashboard or maturity-summary update.

## Readiness Read
- RFQ Gold now includes manifest-level source-quote evidence in addition to the earlier local RFQ corpus.
- Supplier Intelligence now captures source-quote entry references from the manifest layer so the pack can grow past the earlier ceiling without touching runtime logic.
- Pricing Intelligence is expanded from the local high-confidence pricing corpus and remains advisory-only.
- Tender-Win Intelligence now includes award-confirmed records from public award notices, with the original governed outcome history retained alongside it.

## Open Notes
- Supplier references remain source-derived strings in several records and will benefit from future normalization into a supplier master layer.
- Province coverage is still advisory because a subset of source artifacts lacks explicit province labeling.
- Lead times remain source-dependent and are not always explicit in the local evidence corpus.
