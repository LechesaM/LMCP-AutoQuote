# Supervised-Live Pilot Wave 001

## Recommended Initial Shape
- Start with `1` live RFQ, not `3`
- Use the strongest governed supply candidate first
- Expand only after reviewing the first live evidence set

## Selected First Candidate
- `RFQ_002`
- category: `household_products`
- recommendation in the evidence set: `GO`
- rationale: strongest supply candidate in the supervised-live evidence review

## Deferred Candidates
- `RFQ_004`
  reason: supervised supply case, but weaker first-wave candidate than `RFQ_002`
- `RFQ_005`
  reason: physical submission complexity remains operator-heavy

## Required Pre-Run Assignments
- primary operator: `supervisor`
- backup operator: `operator`
- submission portal or channel: `Metro Procurement Unit (portal)`
- pricing file path: `/Users/cash/Documents/runtime/manual_production/submission_packages/REAL-PILOT-001/REAL-PILOT-001__manual_pricing_restored_from_governed_quote_pack.json`

## Evidence Note
- The original generated-package manual pricing JSON referenced by the governed approval trail is no longer present on disk.
- Wave 001 dry-run intake therefore uses a restored structured pricing file derived from the approved governed quote-pack rows.
- The completed buyer pricing schedule CSV remains part of the submission package, but it is not the automation input consumed by `scripts/run_manual_pilot.py`.

## Source Bundle Review
- current status: `REPAIRED AND REVALIDATED`
- repaired tender root: `/Users/cash/Documents/runtime/manual_production/source_bundle_repairs/REAL-PILOT-001`
- original issue: the surviving placeholder source PDF was ASCII text and the first dry run extracted `0` verified line items
- repaired dry-run result: `pending_human_approval` with `extracted line item count = 1`, `pricing items matched = 1`, and `warnings = none`
- implication: Wave 001 may return to operator review, but approval still requires immediate review of the final pricing schedule, compliance package, and submission documents

## Approval Discipline
- Do not run `scripts/approve_manual_pilot.py --confirm-approval` until the operator has just reviewed:
  - the final pricing schedule
  - the compliance package
  - the submission documents
- Approval must remain tied to actual review, not a routine click-through.

## Wave 001 Success Criteria
- submission completed successfully
- no compliance issues discovered during submission
- no pricing-file discrepancies
- no manual overrides required due to system errors
- submission proof recorded correctly
- audit trail complete

Award outcome is not the immediate Wave 001 success criterion.

## Next Execution Sequence
1. Review [supervised_live_pilot_wave_001.json](/Users/cash/Documents/docs/supervised_live_pilot_wave_001.json:1) and confirm the Wave 001 assignments.
2. Run `scripts/run_manual_pilot.py` for `REAL-PILOT-001`.
3. Record approval with `scripts/approve_manual_pilot.py --confirm-approval`.
4. Perform attended manual submission.
5. Record proof with `scripts/record_manual_submission_proof.py`.
6. Review the live evidence before any scope expansion.
