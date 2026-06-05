# Business Intelligence Expansion Pack

## Purpose
This pack assembles evidence-backed non-runtime business-intelligence assets from local repo artifacts only.

## Scope
- Advisory data only.
- No execution-layer changes.
- No workflow-control changes.
- No runtime recertification actions.

## Dataset Counts
- RFQ Gold Dataset scenarios: 53
- Supplier Intelligence records: 100
- Pricing Intelligence lines: 360
- Tender-Win Intelligence records: 120

## Governance Note
Tender-win records in this pack are drawn from local governed submission and outcome evidence. They are useful intelligence inputs, but they are not promoted here as external award confirmations.

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
- `index.json`
- `index.yaml`
- `consistency_review.md`
