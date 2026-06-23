# Operational Readiness Validation Plan

## Purpose
Define the validation scenarios LMCP should pass before any future orchestration isolation or queue partitioning work. This plan is documentation-only and does not change runtime behavior.

## Validation scenarios

### Acquisition failures
- Simulate source discovery failure, portal reachability failure, and raw document fetch failure.
- Expected telemetry: acquisition error event, correlation ID preserved, source health degraded, no downstream pricing or submission trigger.
- Expected state transitions: acquisition remains in failed or retryable state; downstream domains stay untouched.
- Expected escalation: retry if eligible, otherwise operator review.
- Rollback expectation: no business state should advance.
- Operator intervention: investigate source health and retry policy.

### Extraction failures
- Simulate OCR failure, PDF parse failure, BOQ normalization failure, and extraction confidence collapse.
- Expected telemetry: extraction failure event, confidence warnings, stale-data protection where applicable.
- Expected state transitions: workflow remains in extraction or review-needed state.
- Expected escalation: retry or human review based on confidence and retry eligibility.
- Rollback expectation: extracted artifacts should remain auditable and re-processable.
- Operator intervention: inspect raw documents and extraction outputs.

### Pricing failures
- Simulate supplier scoring failure, margin calculation failure, validation failure, and pricing timeout.
- Expected telemetry: pricing failure event, retry policy visibility, pricing state marked degraded or failed.
- Expected state transitions: no approval or submission readiness should be granted.
- Expected escalation: retry if safe, otherwise pricing review.
- Rollback expectation: no quote should be considered final.
- Operator intervention: review pricing inputs, validation output, and supplier assumptions.

### Submission failures
- Simulate portal login failure, upload failure, form-fill failure, submission receipt failure, and portal timeout.
- Expected telemetry: submission failure event, irreversible-operation warning, proof capture visibility, no silent success.
- Expected state transitions: submission remains pending, blocked, or failed; never falsely completed.
- Expected escalation: operator review is required for irreversible or ambiguous outcomes.
- Rollback expectation: no duplicate submission should be triggered automatically.
- Operator intervention: inspect portal state, proof artifacts, and retry eligibility.

### Queue congestion
- Simulate backlog growth, retry backlog, blocked work, and delayed dequeueing.
- Expected telemetry: queue depth increase, blocked job count increase, stale-worker detection if applicable.
- Expected state transitions: jobs remain queued or retry pending until capacity returns.
- Expected escalation: governance alert and operator dashboard visibility.
- Rollback expectation: backlog should not mutate business state.
- Operator intervention: scale workers or clear blocked work.

### Worker crashes
- Simulate worker heartbeat loss, task interruption, and stale worker detection.
- Expected telemetry: stale-worker event, missing heartbeat alert, queue health degraded.
- Expected state transitions: in-flight jobs become recoverable or retryable according to policy.
- Expected escalation: governance alerts and possible job requeue.
- Rollback expectation: failed tasks should not be marked complete.
- Operator intervention: restart workers, inspect failed tasks, and reconcile queue state.

### Retry storms
- Simulate repeated retryable failures across multiple jobs.
- Expected telemetry: retry count growth, retry-delay visibility, queue degradation warning.
- Expected state transitions: jobs move through retry pending and fail when limits are reached.
- Expected escalation: operator intervention once retry thresholds are exceeded.
- Rollback expectation: retry loops should not duplicate irreversible actions.
- Operator intervention: pause affected queue or investigate root cause.

### Dead-letter escalation
- Simulate a job exceeding max attempts or being explicitly diverted to DLQ.
- Expected telemetry: DLQ item visible, source job linked, archive status tracked.
- Expected state transitions: job exits active queue and enters dead-letter retention.
- Expected escalation: governance visibility and operator review.
- Rollback expectation: DLQ entry should be recoverable if safe, otherwise retained for audit.
- Operator intervention: decide retry, archive, or manual remediation.

### Stale RFQ recovery
- Simulate an RFQ whose telemetry or workflow state is stale compared with the last safe snapshot.
- Expected telemetry: stale-data warning, last-safe snapshot reference, degraded status.
- Expected state transitions: operational state marked degraded, business state not mutated automatically.
- Expected escalation: recovery or refresh action requested.
- Rollback expectation: last safe snapshot should remain available.
- Operator intervention: confirm whether to resume, reprocess, or hold.

### Partial workflow completion
- Simulate acquisition completed but extraction incomplete, or pricing completed but submission blocked.
- Expected telemetry: partial completion indicators, stage-specific progress, missing downstream handoff visibility.
- Expected state transitions: upstream stage marked complete, downstream stage pending or blocked.
- Expected escalation: operator review where the handoff is ambiguous.
- Rollback expectation: completed upstream work should remain auditable and not be lost.
- Operator intervention: complete missing stage or reconcile the partial handoff.

## Validation dimensions

### Expected telemetry
- Correlation ID across every event.
- Stage-specific event categories.
- Queue depth, retry counts, DLQ counts, stale-worker counts.
- Failure category and escalation level.
- Last safe snapshot visibility when applicable.

### Expected state transitions
- Each domain should transition only within its authority boundary.
- Failed or stale states should not auto-progress to success.
- Retry should preserve original context and attempt count.
- Dead-lettered work should leave active execution paths.

### Expected escalation paths
- Automatic retry for safe transient failures.
- Human review for ambiguous or irreversible failures.
- Governance alert for queue or worker health degradation.
- DLQ escalation for exhausted retries or unsafe failures.

### Rollback expectations
- Rollback should preserve auditability.
- Rollback must not delete proof, receipt, or audit artifacts.
- Rollback must not auto-resubmit or reprice without explicit operator action.

### Operator intervention points
- Acquisition source review.
- Extraction repair or re-run.
- Pricing validation or manual review.
- Submission portal review and approval.
- Queue recovery, worker restart, and DLQ handling.

## Production readiness gates
- Health, status, queue, and worker telemetry must be available.
- Correlation IDs must be present in logs and recovery reports.
- Stale-data protection must preserve the last safe snapshot.
- DLQ visibility must be present before enabling broader orchestration isolation.
- Submission dry-run validation must be available before any real submission isolation.

## Operational acceptance criteria
- Failure scenarios must fail closed.
- No silent success on broken handoffs.
- No duplicate irreversible actions during retry.
- No missing telemetry for queue backlog, worker health, or DLQ state.
- Operator can trace a single RFQ from acquisition through submission or failure.

## Recovery-time expectations
- Transient queue or worker issues should be visible immediately.
- Retryable task failures should be visible within the next telemetry cycle.
- DLQ and stale-state visibility should be available without manual log inspection.
- Operator intervention should be possible before irreversible submission steps are repeated.

## Observability requirements
- Structured logs for request, task, and orchestration events.
- Queue telemetry and worker heartbeat visibility.
- RFQ lifecycle and correlation tracing.
- DLQ and recovery reporting.
- Last safe snapshot visibility for stale runtime data.

## Safest testing order
1. Validate read-only telemetry and stale-data guards.
2. Validate acquisition and extraction failure handling.
3. Validate pricing failure and retry behavior.
4. Validate queue congestion and worker crash visibility.
5. Validate DLQ escalation and recovery reporting.
6. Validate submission dry-run behavior before any live submission isolation.

## Shadow-mode strategy
- Run orchestration visibility in shadow mode against live state without changing business outcomes.
- Compare queue telemetry, workflow state, and DLQ state against the authoritative runtime state.
- Use shadow validation to detect hidden coupling before any future isolation.

## Dry-run strategy for submission flows
- Simulate submission handoffs and portal interactions without executing irreversible actions.
- Require approval and go-live guard checks in the dry-run payload.
- Verify that dry-run telemetry matches the real submission contract without transmitting to external portals.

## Constraint
- This plan is for validation only. It does not change orchestration, queue topology, or business logic.

