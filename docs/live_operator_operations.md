# Live Operator Operations

## Purpose
This branch adds governed operator operations to the LMCP Command Centre.
It expands operator visibility into actionable, auditable workspace flows without introducing autonomous execution.

## Controlled Operator Actions
The operator workspace supports the following manual actions:
- `assign_operator`
- `mark_reviewed`
- `request_clarification`
- `archive_rfq`
- `mark_evidence_incomplete`
- `mark_supplier_quote_received`
- `mark_waiting_pricing`
- `escalate_review`
- `reopen_review`
- `acknowledge_alert`

Each action:
- requires an explicit `operator_id`
- targets a specific RFQ or alert
- creates an append-only audit event
- creates an activity timeline event
- remains reversible or reviewable where applicable

## Assignment Behavior
Assignment recommendations are advisory only.
The system keeps capacity assumptions at:
- 10 operators
- 100 RFQs per operator per day
- 1,000 RFQs total per day

No automatic promotion or enforcement bypass is introduced.

## Notifications
Notifications remain advisory and cover:
- stale RFQs
- overdue reviews
- source failures
- queue overload
- stale evidence
- governance warnings
- parser failures
- operator assignment reminders

## Audit and Timeline Guarantees
Every operator action creates:
- an audit record
- a timeline event

The timeline is append-only and reviewable.

## Governance Preservation
This release preserves:
- manual approval
- `review_ready`
- proof capture
- manual-only final submission
- pricing thresholds
- workflow transition rules

## Operational Limitations
The operator workspace is not allowed to:
- auto-approve RFQs
- auto-transition workflows
- submit tenders
- bypass proof capture
- bypass review
- bypass manual governance

## Read-Only / Manual Boundary
Operator actions are governed and intentional.
They do not create autonomous procurement execution or hidden workflow mutation.
