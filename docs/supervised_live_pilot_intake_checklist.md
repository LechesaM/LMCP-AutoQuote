# Supervised-Live Pilot Intake Checklist

Use this checklist before admitting any RFQ into the first supervised-live pilot wave.

## Pilot Wave Limits
- RFQs in wave: `1-3`
- Tier 25: frozen
- Track A: `WAIT`
- Track B: `MONITOR`

## RFQ Intake Record
- Tender ID:
- Tender root:
- Pricing file:
- Operator owner:
- Backup operator:
- Portal or channel:
- Submission mode: manual only

## Admission Checks
- Tier 10 gate is `eligible_for_supervised_live`
- RFQ is a clean governed supply case
- Quote-pack readiness is acceptable
- No unresolved critical blocker exists
- Operator is available for attended submission
- Proof capture path is known before submission

## Exclusion Checks
- Technical validation still unresolved
- Physical submission path still unclear
- Supplier evidence is materially incomplete
- Submission path cannot be fully attended

## Required Script Order
1. `scripts/run_manual_pilot.py`
2. `scripts/approve_manual_pilot.py --confirm-approval`
3. attended manual submission by operator
4. `scripts/record_manual_submission_proof.py`

## Stop Conditions
- critical failure
- governance bypass
- approval missing
- proof missing
- rollback invoked due to incorrect live action

## Signoff
- Operator:
- Supervisor:
- Date:
