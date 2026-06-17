# Controlled Operation Checklist

## Purpose
Define the minimum evidence required before the system is treated as ready for controlled operation.

This checklist is not an authorization to expand scope. It is a gate for judging whether the narrow supervised pilot can continue without hidden drift.

## Minimum Conditions
- The supervised pilot path is runnable through a single command.
- Dry-run intake, manual approval, review generation, and proof capture are all available.
- The operator can explain which RFQ, which pricing file, and which proof file are authoritative.
- The current runbook names a single narrow candidate and a single operator.
- The readiness report is stable and reviewable before each session.

## Controlled Operation Thresholds
- Pilot readiness score is at least `80`.
- At least one successful pilot run is recorded.
- At least one approval signoff is recorded.
- At least one proof signoff is recorded.
- Failed runs, if any, have been reviewed before expanding scope.
- Required controlled-operation docs are present:
  - `docs/controlled_operation_checklist.md`
  - `docs/supervised_live_pilot_runbook.md`
  - `docs/supervised_live_daily_checklist.md`

## What Still Blocks Completion
- A fresh live RFQ feed that reuses the same narrow path without manual repair.
- Repeatable multi-day proof from new live runs.
- A documented rollback and incident recovery drill that has been exercised on a live operator session.
- A formal acceptance bar for expansion beyond the first narrow candidate.
- A verified commercial submission channel that has been repeated on fresh evidence.

## Recommended Operator Check
Run the controlled-operation readiness checker before each session:

```bash
python3 scripts/check_controlled_operation_readiness.py
```

For the full JSON payload:

```bash
python3 scripts/check_controlled_operation_readiness.py --json
```

## Decision Rule
- `READY` means the narrow supervised pilot can continue under the same controls.
- `NOT READY` means keep the system in supervised pilot mode and fix the blockers first.
- This checklist does not authorize autonomous submission.

## Controlled Pilot Stages

### Stage 1

Run `5` RFQs, then `10`, then `25`.

### Stage 2

Use the pilot dashboard as the go/no-go indicator. It must show:

- RFQs Harvested
- RFQs Rejected
- RFQs Approved
- Quote Packs Generated
- Submission Records
- Proof Records
- Pilot Success Rate

### Stage 3

Treat the platform as a production candidate only after `25-50` successful RFQs with:

- no persistence failures
- no proof-chain failures
- no submission-history failures

### Stage 4

Autonomous expansion remains blocked until the pilot evidence is sufficient and human approval remains in place.
