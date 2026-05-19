# Supervised-Live Pilot Plan

## Purpose
Prepare and run a controlled supervised-live pilot for 10 real valid RFQs under manual-production governance.

## Scope
- Pilot set size: 10 valid RFQs
- Operating mode: supervised-live only
- Workflow scope: existing approval, review, proof, and refusal rules
- Exclusions: no workflow redesign, no autonomous submission, no bypass of manual approval, no bypass of submission review, no bypass of proof capture

## Supervised-Live Definition
Supervised-live means an operator remains responsible for every control point, every approval checkpoint, every review checkpoint, and every proof-capture checkpoint.
The system may assist with reporting and readiness summaries, but final submission remains manual-only.

## Operator Responsibilities
- Confirm each RFQ is valid before pilot processing
- Track each RFQ through the controlled workflow
- Record approval, review, and proof checkpoints
- Capture evidence for all manual actions
- Escalate any workflow irregularity immediately

## Approval Responsibilities
- Confirm manual approval before advancing a quote pack
- Confirm approval sign-off is recorded
- Confirm no skipped approval path exists

## Review Responsibilities
- Confirm review_ready status before proof capture
- Confirm submission review remains human-controlled
- Confirm review sign-off is recorded

## Proof Capture Responsibilities
- Capture proof only after review_ready
- Preserve proof artifacts in the manual-production workspace
- Confirm proof sign-off is recorded

## Escalation Path
- Escalate workflow failures to the operator lead
- Escalate persistence failures to engineering support
- Escalate governance concerns to the pilot owner
- Pause the pilot if any control bypass is suspected

## Go/No-Go Conditions
- Go when workflow integrity, evidence capture, and manual governance are functioning as expected
- No-go when workflow skipping, proof skipping, or submission skipping is detected

## Stop Conditions
- Any autonomous final submission attempt
- Any bypass of manual approval
- Any bypass of submission review
- Any bypass of proof capture
- Any persistence failure that threatens auditability
- Any unresolved governance discrepancy

## Final Submission Rule
Final submission remains manual-only for the entire supervised-live pilot.
