# Weekly Dry-Dispatch Evidence Registry

## Purpose
Capture operational evidence for the execution layer without changing Track A, Track B, workflow structure, or dashboard scope.

## Required Weekly Metrics
- Pass Rate
- Gate Score
- Confidence Score
- Retry Rate
- Rollback Rate
- Top Failure Category
- Production Ready Status

## Suggested Run Commands
Run with the fixed Tier 10 manifest auto-resolution:

```bash
python3 scripts/run_weekly_dry_dispatch_cycle.py \
  --tier-label tier_10 \
  --week-ending 2026-06-07 \
  --print-gate
```

Run against an explicit manifest when needed:

```bash
python3 scripts/run_weekly_dry_dispatch_cycle.py \
  --tier-label tier_25 \
  --manifest tests/fixtures/manifests/tier_25.json \
  --week-ending 2026-06-14 \
  --print-gate
```

## Fixed Tier Manifests
- Tier 10: `tests/fixtures/manifests/tier_10.json`
- Tier 25 draft: `tests/fixtures/manifests/tier_25.json`

## Registry Outputs
- JSONL history: `runtime/execution_evidence/weekly_dry_dispatch_registry.jsonl`
- Latest report: `runtime/execution_evidence/latest_dry_dispatch_report.json`

## Operating Rule
- Do not change Track A or Track B as part of this evidence cycle.
- Use the top failure category from the registry to drive the next failure-reduction sprint.
