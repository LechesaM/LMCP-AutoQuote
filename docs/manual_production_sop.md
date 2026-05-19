# Manual Production SOP

## Definition

Manual production is the controlled operating mode in which operators process RFQs under human governance. The system may assist, but it must not submit work autonomously.

## Daily Startup Checklist

- Confirm the current branch and deployment target are correct.
- Confirm runtime directories exist.
- Confirm `/health` and the internal health endpoints report acceptable status.
- Confirm dashboard queues are visible and empty or understood.
- Confirm audit logging is available.
- Confirm the latest validation and readiness checks completed successfully.

## Daily Shutdown Checklist

- Confirm all pending RFQs are either advanced, refused, or explicitly parked.
- Confirm proof capture is complete for submitted RFQs.
- Confirm audit and workflow logs are flushed to disk.
- Confirm unresolved warnings are documented for the next shift.
- Confirm backup or archive tasks have completed if scheduled.

## Operator Responsibilities

- Review RFQs and supporting documents.
- Record approvals only when prerequisites are met.
- Review submissions before proof capture.
- Refuse blocked or out-of-policy RFQs.
- Escalate missing artifacts or system failures.
- Keep records truthful and append-only.

## Allowed Actions

- Evaluate RFQs
- Approve quote packs
- Record review readiness
- Capture proof after review readiness
- Refuse RFQs
- Archive refused or completed workflows
- Add operator notes and warning acknowledgements

## Prohibited Actions

- Autonomous final submission
- Bypassing approval or review stages
- Forcing workflow transitions around the engine
- Editing audit history
- Deleting operational logs

## Audit Requirements

- Every material workflow action must be traceable.
- Operator notes and approvals must be auditable.
- Refusals and archives must be recorded.
- Missing audit evidence is a production issue.

