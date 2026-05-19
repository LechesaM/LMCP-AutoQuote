# Workflow Recovery SOP

## Purpose
This SOP describes how operators recover queued jobs and workflow states safely when manual-production processing is interrupted or stalled.

## Recovery Principles
- Recovery is read-first and operator-driven.
- Workflow integrity takes priority over throughput.
- No recovery action may skip workflow stages.
- No recovery action may enable autonomous submission.
- Append-only history must be preserved.

## Recovery Triggers
- Stuck queue jobs
- Failed queue jobs
- Blocked queue jobs
- Orphaned workflow states
- Persistence mismatches
- Missing audit evidence

## Operator Workflow
1. Review queue health and recovery candidates.
2. Confirm whether the job or workflow is eligible for recovery.
3. Choose a bounded action:
   - retry failed job
   - archive failed job
   - mark job blocked
   - acknowledge warning
4. Record the action and preserve the audit trail.

## Safety Rules
- Never bypass approval_required.
- Never bypass approved.
- Never bypass review_ready.
- Never bypass proof_recorded requirements.
- Never create final submission automation.
- Never overwrite recovery history without explicit operator action.

## Recovery Outcomes
- Retry when the failure is bounded and retryable.
- Archive when the job or workflow cannot safely resume.
- Block when operator review is needed before further action.

## Escalation
- Escalate any recovery case involving corrupted workflow history.
- Escalate any mismatch between queue state, workflow state, and persistence history.
- Escalate any case that suggests duplicate or unintended submission processing.

