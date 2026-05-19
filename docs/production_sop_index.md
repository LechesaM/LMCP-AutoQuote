# Production SOP Index

## Purpose

This index collects the operator SOPs for controlled manual production use of LMCP AutoQuote. It is the entry point for day-to-day operation, validation, recovery, and escalation.

## Who Should Use It

- Operators handling RFQs
- Approvers and reviewers
- Proof capture operators
- Shift leads and production supervisors
- Support staff responsible for monitoring and recovery

## Manual-Production Operating Principle

Manual production is the authoritative operating mode. Human approval controls the workflow, and no autonomous final submission is permitted.

## SOP List

- [Manual Production SOP](./manual_production_sop.md)
- [RFQ Processing SOP](./rfq_processing_sop.md)
- [Quote Approval SOP](./quote_approval_sop.md)
- [Submission Review SOP](./submission_review_sop.md)
- [Proof Capture SOP](./proof_capture_sop.md)
- [Operator Dashboard SOP](./operator_dashboard_sop.md)
- [Health Monitoring SOP](./health_monitoring_sop.md)
- [E2E Validation SOP](./e2e_validation_sop.md)
- [Failure Recovery SOP](./failure_recovery_sop.md)
- [No Autonomous Submission Policy](./no_autonomous_submission_policy.md)
- [Go-Live Checklist](./go_live_checklist.md)

## Production Safety Rules

- Final submission remains manual-only.
- Approval, review, and proof capture must follow the workflow engine.
- Refusals and archives are explicit and append-only.
- Monitoring and dashboard views are read-only except for approved operator actions.
- JSONL and durable persistence are compatibility layers, not workflow overrides.

