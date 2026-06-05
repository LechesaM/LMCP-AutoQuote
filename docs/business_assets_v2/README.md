# Business Intelligence Expansion Pack v2

## Purpose
This pack extends the non-runtime intelligence layer using local repository evidence, manifest-level source-quote provenance, and public award notices.

## Scope
- Advisory data only.
- No execution-layer changes.
- No workflow-control changes.
- No runtime recertification actions.

## Dataset Counts
- RFQ Gold Dataset scenarios: 247
- Supplier Intelligence records: 294
- Pricing Intelligence lines: 500
- Tender-Win Intelligence records: 217

## Governance Note
This pack explicitly carries provenance, verification status, last review date, reviewed by, and source reference metadata on every intelligence record.
Award-confirmed tender wins are present only where a public award notice or equivalent publication is available.
Tender-win verification status is explicit across the full dataset: Award Confirmed, Verified, or Derived.

## Validation
- JSON index validated: True
- YAML index validated: True
- Placeholder scan passed: True
- Evidence-path check passed: True

## Files
- `datasets/rfq_gold_dataset.jsonl`
- `datasets/supplier_intelligence.jsonl`
- `datasets/pricing_intelligence.jsonl`
- `datasets/tender_win_intelligence.jsonl`
- `sources/award_confirmed_sources.json`
- `province_supplier_map.md`
- `competitor_intelligence.md`
- `opportunity_scorecard.md`
- `win_probability_methodology.md`
- `win_probability_calibration.md`
- `index.json`
- `index.yaml`
- `consistency_review.md`
