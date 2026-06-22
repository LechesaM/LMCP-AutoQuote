# LMCP Sprint 7 - Pilot Dashboard Specification

## Scope

The pilot dashboard tracks operational behavior during the controlled live pilot.

## Throughput Metrics

Capture daily:

- `rfqs_harvested`
- `rfqs_qualified`
- `rfqs_rejected`
- `quote_packs_generated`
- `submission_packs_generated`
- `submission_packs_approved`

## Qualification Metrics

Capture:

- `qualification_accuracy`
- `false_positive_count`
- `false_negative_count`
- `top_rejection_codes`

Target:

- `qualification_accuracy >= 95%`

## Governance Metrics

Capture:

- `approval_gate_bypass_count`
- `submission_ready_without_approval_count`
- `duplicate_audit_events`
- `orphaned_audit_events`
- `state_drift_count`

Target:

- all values remain `0`

## Submission Metrics

Capture:

- `submission_pack_success_rate`
- `submission_pack_block_rate`
- `average_readiness_score`
- `top_blocking_codes`

Track weekly trends and week-over-week deltas.

## Approval Metrics

Capture:

- `approval_turnaround_time`
- `average_review_duration`
- `approval_rate`
- `rejection_rate`

## Operator Feedback Metrics

Capture:

- `operator_disagreement_count`
- `disagreement_category`
- `reason_for_override`
- `suggested_rule_improvements`

Categories:

- Qualification
- Compliance
- Packaging
- Governance
- Usability

## Review Cadence

Weekly review agenda:

- throughput
- qualification
- governance
- audit
- operator feedback

