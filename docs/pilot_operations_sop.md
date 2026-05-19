# Pilot Operations SOP

## Purpose
This SOP defines how supervised pilot operations are run for LMCP AutoQuote when real RFQs are used under manual-production governance.
The supervised-live pilot pack supports operational execution only and does not alter workflow rules, refusal rules, or pricing thresholds.

## Pilot Workflow
1. Confirm pilot mode.
2. Load a real RFQ under operator supervision.
3. Evaluate exclusions and pricing thresholds.
4. Generate quote artifacts only when eligible.
5. Record manual approval, review, and proof sign-offs where required.
6. Record the pilot run and operational outcome.
7. Review readiness and operator warnings.

## Operator Responsibilities
- Keep pilot mode supervised.
- Confirm every approval checkpoint.
- Confirm review-ready and proof-capture requirements.
- Refuse non-eligible RFQs.
- Record pilot failures and recovery actions.

## Pilot Success Criteria
- RFQ processing remains within normal procurement rules.
- No autonomous final submission occurs.
- Approval and review checkpoints remain human-confirmed.
- Proof capture is recorded after review-ready only.
- Pilot records are auditable and append-only.

## Refusal Handling
- Refuse RFQs that are excluded or below threshold.
- Refuse any pilot operation that attempts to skip workflow stages.
- Record the refusal reason and preserve the audit trail.

## Failure Escalation
- Escalate workflow failures.
- Escalate persistence failures.
- Escalate operator warnings that suggest bypass attempts or duplicate submissions.

## Readiness Interpretation
- Readiness scores are informational only.
- A high readiness score does not authorize autonomous execution.
- A low readiness score indicates the pilot should remain supervised or paused.

## Go/No-Go Criteria
- Go only when human supervision, workflow integrity, and proof capture are consistently correct.
- No-go if any autonomous submission behavior is observed or suspected.
- Final submission remains manual-only in all supervised-live pilot operations.
