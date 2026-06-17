# Supervised-Live Pilot Wave 002

## Controlled Scope
- initial live RFQ count: `1`
- maximum live RFQ count without a new formal note: `2`
- Tier 25: `frozen`
- Track A: `WAIT`
- Track B: `MONITOR`
- Regression Run #2: untouched

## Selected Initial Candidate
- `RFQ_004`
- buyer: `South African Forestry Company SOC Ltd (SAFCOL)`
- category: `equipment_supply`
- submission path: `portal with email fallback`
- rationale:
  - cleanest admissible next supervised supply candidate after Wave 001
  - lower operator burden than courier/hand-delivery-only handling
  - no technical validation required in the fixture evidence
  - suitable for continued governed learning under manual controls

## Authorized Next Candidate
- `RFQ_005`
- status: `AUTHORIZED`
- reason: it is the correct next governed test because it adds operator-heavy submission complexity without expanding autonomy

## Restrictions Preserved
- human approval required
- manual submission required
- operator-attended submission only
- proof capture required
- retry and rollback tracking required
- no autonomous final submission

## Linked Remediation
- `REM-QUOTE-COMPARISON-ENRICHMENT-001`
- remediation review outcome: `PASS`
- fix must occur outside the monitoring layer

## Next Execution Gate
1. Prepare `RFQ_005` readiness under the same supervised-live sequence used in Wave 001 and Wave 002.
2. Run dry-run readiness validation.
3. Prepare human review and approval recording.
4. Execute attended manual submission and immediate proof capture.
5. Record postmortem review and formal outcome.

## Preflight Requirements

### Evidence Readiness
- submission package generated
- pricing package generated
- compliance package generated
- no unresolved warnings
- no unresolved errors

Current status:
- `CONFIRMED`
- Submission package generation: confirmed
- Pricing package generation: confirmed
- Compliance package generation: confirmed
- No unresolved warnings: confirmed
- No unresolved errors: confirmed
- Package area normalized under `runtime/manual_production/submission_packages/RFQ_004`
- Compliance package is a governed operator-review checklist artifact and does not replace the required final operator review of live compliance documents.

### Operator Assignment
Record before execution:
- `operator_owner`
- `backup_operator`
- `submission_channel`
- `escalation_contact` (optional but useful)

Current status:
- operator_owner: `supervisor`
- backup_operator: `operator`
- submission_channel: `portal with email fallback`
- escalation_contact: `procurement@safcol.co.za`

### Governance Check
Verify before execution:
- Wave 001 outcome remains recorded
- Tier 25 still frozen
- Track A unchanged
- Track B unchanged

Current status:
- Wave 001 outcome: `PASS WITH OBSERVATIONS`
- Tier 25: `frozen`
- Track A: `WAIT`
- Track B: `MONITOR`
- Regression Run #2: untouched

## Wave 002 Success Criteria
- The supervised workflow executes without process defects.
- Human review remains effective.
- Approval chain remains intact.
- Proof capture remains intact.
- No new material governance issues appear.
- Quote-comparison remediation remains the only known observation.

## Current Program Status
- Wave 001: `PASS WITH OBSERVATIONS`
- Wave 002: `PASS WITH OBSERVATIONS`
- Quote Comparison Remediation: `PASS`
- RFQ_005: `AUTHORIZED`
- Tier 25: `frozen`
- Track A: `WAIT`
- Track B: `MONITOR`
- Regression Run #2: untouched
- Multi-RFQ Expansion: `NOT AUTHORIZED`

## Not Allowed Yet
- Do not unfreeze Tier 25 automatically.
- Do not allow unattended submissions.
- Do not activate multi-RFQ expansion automatically.
- Do not modify Track A.
- Do not modify Track B.
- Do not modify Regression Run #2.
