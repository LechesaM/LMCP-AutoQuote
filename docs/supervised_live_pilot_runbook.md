# Supervised-Live Pilot Runbook

## Purpose
Move from Tier 10 stability evidence into a tightly controlled supervised-live pilot.

This runbook does not authorize autonomous submission.

## Fixed Constraints
- Tier 25 remains frozen.
- Track A remains `WAIT`.
- Track B remains `MONITOR`.
- Regression Run #2 remains untouched.
- Final submission remains operator-attended and manual-only.

## Pilot Scope
- Live RFQs allowed in the first pilot wave: `1-3`
- Every live RFQ requires explicit operator approval before submission activity
- No unattended submission is allowed
- Full audit evidence is required for every live RFQ
- Retry and rollback tracking must remain active
- Any critical failure pauses the pilot immediately

## Controlled MVP Validation Sequence

Use one real supply-and-delivery RFQ first, then expand to a small batch of `5-10` live RFQs only if the first case passes.

### End-to-End Path
1. Harvest.
2. Persist.
3. Extract.
4. Eligibility gate.
5. Pricing.
6. Quote pack.
7. Approval.
8. Submission.
9. Proof record.

### Required Submission History Fields
- `proof_path`
- `submission_channel`
- `buyer_confirmation_reference`
- `receipt_text`
- `receipt_timestamp`
- `submitted_files`

### Pass Criteria
- The RFQ reaches proof capture with no hidden repair step.
- The submission history record contains the proof-chain fields.
- Operator approval is explicit and recorded.
- Final submission remains human-approved.
- If the RFQ is rejected, the rejection reason is written down before the next case is selected.

## Entry Criteria
- Tier 10 dry-dispatch registry shows `4 / 4` qualifying active weeks
- Gate status is `eligible_for_supervised_live`
- Operator and supervisor agree on the initial `1-3` live RFQs
- Each selected RFQ has a documented owner and fallback operator

## RFQ Selection Rules
Prefer the cleanest governed supply cases:
- clear supply category
- strong quote-pack readiness
- no unresolved blocker in the dry-dispatch evidence
- operator-accessible submission path

Do not include:
- technical fabrication RFQs requiring manual engineering validation
- physical-submission-heavy tenders without stable operator handling
- RFQs with unresolved critical evidence gaps

## Required Operator Sequence
For each live RFQ:

### One-Command Wrapper
For a narrow pilot workspace folder, you can use the supervised pilot wrapper to run the dry-run, record the approval gate, and optionally record proof after the manual submission:

```bash
python3 scripts/run_supervised_pilot_week.py \
  --workspace-root <WORKSPACE_ROOT> \
  --pilot-id <PILOT_ID> \
  --confirm-approval \
  --operator-name <OPERATOR_NAME> \
  --pricing-file <PRICING_JSON> \
  --record-proof \
  --portal-name <PORTAL_OR_CHANNEL> \
  --submission-reference <REFERENCE> \
  --proof-file <PROOF_FILE>
```

Use the same command without `--record-proof` before the live submission happens. The wrapper still records the dry-run and manual approval state, then pauses with `record proof after the live manual submission` as the next step.

For the quickest approval-only check, `make pilot-week-dry-run` runs the same narrow candidate without proof capture.

For the daily operator loop, `make daily-pilot-loop` selects the best available RFQ bundle, runs the narrow supervised flow, writes `runtime/manual_production/daily_pilot_loop_report.json`, and prints a concise operator report.

For the start-of-day ritual, `make morning-ritual` runs the readiness check first, prints the live queue status, and fails fast if the queue is empty before doing any loop work. If the queue has runnable work, it launches the daily operator loop in fresh-only mode. If the queue has no fresh runnable candidate, the ritual now fails fast instead of falling back to repeat work or a local fixture.

Use `make queue-refresh` separately when you want to seed the queue from the National Treasury eTenders source. Use `make fresh-intake` when you want the fallback fixture recovery path.

### 1. Dry-Run Intake
Run the assisted-production dry run first.

```bash
python3 scripts/run_manual_pilot.py \
  --tender-id <TENDER_ID> \
  --tender-root <TENDER_ROOT> \
  --pricing-file <PRICING_JSON> \
  --pilot-workspace-root <WORKSPACE_ROOT> \
  --pilot-workspace-id <PILOT_ID>
```

Required outcome:
- no critical error
- quote pack generated
- submission pack generated
- approval blocked is `false`

### 2. Operator Approval
Record explicit operator approval before any live submission action.

Approval is prohibited unless the operator has just reviewed all of the following:
- final pricing schedule
- compliance package
- submission documents

```bash
python3 scripts/approve_manual_pilot.py \
  --tender-id <TENDER_ID> \
  --tender-root <TENDER_ROOT> \
  --pricing-file <PRICING_JSON> \
  --confirm-approval \
  --operator-name <OPERATOR_NAME> \
  --pilot-workspace-root <WORKSPACE_ROOT> \
  --pilot-workspace-id <PILOT_ID>
```

Required outcome:
- `manual approval recorded: true`
- `submission ready: true`
- `final submission attempted: false`

### 3. Attended Manual Submission
The operator performs the buyer-portal or email submission manually.

Required controls:
- operator is present for the entire submission
- no autonomous final submit
- no unattended browser workflow
- no submission while approval evidence is missing

### 4. Proof Capture
Record proof immediately after the manual submission event.

```bash
python3 scripts/record_manual_submission_proof.py \
  --tender-id <TENDER_ID> \
  --tender-root <TENDER_ROOT> \
  --portal-name <PORTAL_OR_CHANNEL> \
  --submission-reference <REFERENCE> \
  --submitted-by <OPERATOR_NAME> \
  --proof-file <PROOF_FILE>
```

Required outcome:
- proof recorded
- proof file present if available
- final submission attempted remains governed and auditable

## Required Evidence Per RFQ
- dry-run output
- approval output
- manual submission timestamp
- operator name
- portal or channel name
- submission reference
- proof file or proof artifact reference
- retry count
- rollback count
- incident notes

## Wave 001 Success Criteria
Wave 001 is successful only if all of the following are true:
- submission completed successfully
- no compliance issue is discovered during submission
- no pricing-file discrepancy is discovered
- no manual override is required because of a system error
- submission proof is recorded correctly
- audit trail is complete

Award outcome is not the immediate success criterion for Wave 001.

The purpose of Wave 001 is to validate the supervised-live process under operator control.

## Stop Rules
Pause the entire live pilot immediately if any of the following occurs:
- critical submission failure
- governance bypass
- unattended submission attempt
- missing approval evidence
- missing proof capture after a live submission
- rollback required due to incorrect live action

## Review Outcome
After the first `1-3` live RFQs:
- review the pilot evidence before expanding scope
- keep Tier 25 frozen until that review is complete
- decide whether supervised-live testing continues, pauses, or rolls back

Formal Wave 001 review outcome is required before considering:
- Wave 002
- multiple live RFQs
- Tier 25 activation

Allowed formal review outcomes:
- `PASS`
  No material process issues found.
- `PASS WITH OBSERVATIONS`
  Minor issues are present, but the process was successful.
- `HOLD`
  Process defects require remediation before any scope expansion.

## Decision Reminder
Crossing the Tier 10 stability threshold authorizes controlled supervised-live testing only.

It does not authorize autonomous submission.
