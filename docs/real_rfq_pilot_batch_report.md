# Real RFQ Pilot Batch Report

## Objective
Run a controlled real-RFQ pilot batch under manual-production governance.

Constraints preserved:
- No autonomous submission.
- No bypass of approval, review, or proof gates.
- No new workflow architecture.

## Batch Scope
- Input folder: `tests/fixtures/real_pilot_rfqs/`
- RFQs tested: 5
- Passed: 3
- Refused: 2
- Failed: 0

## Validation Commands
- `python3 -m pytest tests/test_e2e_rfq_harness.py -q`
- `python3 -m pytest tests/test_pilot_readiness.py -q`
- `python3 -m pytest tests/test_production_quality_optimization.py -q`
- `python3 -m pytest tests/test_operator_dashboard.py -q`

All four targets passed.

## Quote-Pack Fix
- Previous quote-pack readiness: `0.0`
- New quote-pack readiness on valid RFQs: `1.0`
- Target met: `yes`

## Readiness Summary
- Production readiness score: `80.0`
- Workflow correctness rate: `0.6`
- Persistence verification rate: `1.0`
- Audit verification rate: `1.0`
- Manual-production safety status: `safe`

Supplementary pilot readiness report:
- Pilot readiness score: `60.0`
- Pilot mode: `supervised_live`
- Manual submission remained preserved: `true`

## Per-RFQ Results
| Tender | Outcome | Extraction | Pricing schedule | Quote-pack readiness | Supplier pricing warnings | Operator recommendation | Refusal reasons |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| `REAL-PILOT-001` | passed | `1.0` | `0.6` | `1.0` | none | review workflow | none |
| `REAL-PILOT-002` | passed | `1.0` | `0.6` | `1.0` | none | review workflow | none |
| `REAL-PILOT-003` | passed | `1.0` | `0.6` | `1.0` | none | review workflow | none |
| `REAL-PILOT-004` | refused | `1.0` | `0.6` | `0.0` | none | archive; rerun validation | excluded category |
| `REAL-PILOT-005` | refused | `1.0` | `0.6` | `0.0` | none | archive; rerun validation | minimum profit R30,000 not met; minimum supply margin 25% not met |

## Workflow Failures
- Workflow failures recorded: `0`
- Persistence failures recorded: `0`
- Audit failures recorded: `0`

## Blockers
- Excluded category RFQ remains refused
- Below-margin RFQ remains refused
- No remaining quote-pack readiness blocker for valid RFQs
- Pricing schedule quality remains at `0.6` because the dry-run fixtures only include minimal line-item data

## Recommended Fixes Before `supervised_live`
1. Keep the manual approval, review, and proof gates exactly as they are.
2. Continue refusing excluded and below-margin RFQs instead of trying to force them through the workflow.
3. Keep using dry-run validation on new pilot RFQs before any live supervision session.
4. If future pilot batches need higher schedule quality, enrich line-item schedules with fully populated unit price and total fields.

## Notes
- Supplier pricing warnings were empty for all five fixtures.
- The batch stayed within manual-production safety boundaries.
- The quoted scores reflect the current harness and quality rules, not autonomous submission behavior.
- `manual_production` approval, review, and proof gates remained intact.
