# Controlled Operational Rehearsal Program

## Purpose
Define the controlled operational rehearsal program for LMCP staging validation. This program is documentation only and does not enable live submissions, remove submission protections, use production credentials, or redesign orchestration.

## Rehearsal scenarios

### Normal RFQ processing
- Ingest a small, low-risk RFQ set.
- Run the normal dry-run workflow through acquisition, extraction, pricing, and review preparation.
- Confirm telemetry, audit, and queue visibility remain stable.

### Extraction failure recovery
- Introduce a recoverable document extraction failure.
- Verify the workflow pauses at the expected review or retry boundary.
- Confirm the recovery path preserves audit evidence and correlation IDs.

### Pricing retry recovery
- Introduce a pricing validation failure that requires retry or operator review.
- Confirm pricing does not auto-advance into submission.
- Verify retry and escalation visibility remain clear.

### Queue congestion
- Rehearse a controlled backlog increase in a staging queue.
- Confirm queue depth, backlog age, and retry visibility are surfaced.
- Verify the system remains fail-closed for submission-related steps.

### Worker crash recovery
- Simulate a worker loss or stale heartbeat.
- Confirm the monitoring surfaces show the worker as degraded or offline.
- Verify the workflow remains safe and does not bypass protections.

### Dead-letter escalation
- Force a bounded retry limit to be reached in a rehearsal context.
- Confirm dead-letter handling is visible and preserved.
- Verify no destructive or auto-purging behavior is triggered.

### Approval workflow delays
- Delay approval on a submission-ready rehearsal package.
- Confirm the workflow remains in a review or approval-hold state.
- Verify no submission execution can proceed while approval is pending.

### Rollback drills
- Rehearse returning the workflow to the last safe dry-run state.
- Preserve proof, audit, and guard evidence during rollback.
- Verify rollback does not trigger a live submission or queue mutation outside the rehearsal scope.

### Operator intervention drills
- Require an operator to inspect a blocked or ambiguous rehearsal state.
- Confirm the operator can decide whether to continue, recover, or terminate the rehearsal.
- Verify intervention decisions are auditable.

### Telemetry outage drills
- Simulate partial loss of telemetry or status visibility.
- Confirm the rehearsal is halted or escalated when visibility is insufficient.
- Verify no hidden workflow progression occurs while telemetry is absent.

## Operator responsibilities
- Confirm the rehearsal is using staging-only credentials, queues, and storage.
- Review the scenario setup before the rehearsal begins.
- Monitor each stage transition and guard decision.
- Validate telemetry, audit evidence, and recovery results.
- Stop the rehearsal if any irreversible action becomes possible.

## Escalation paths
- Escalate to operator lead if queue health degrades beyond the rehearsal threshold.
- Escalate to governance if worker heartbeats are lost or telemetry becomes stale.
- Escalate to platform support if a rehearsal cannot preserve rollback evidence.
- Escalate immediately if a submission path appears to be live-capable.

## Rehearsal success criteria
- All rehearsed scenarios complete within the documented dry-run and shadow-mode limits.
- No live submission, live credential use, or irreversible external action occurs.
- Queue, worker, telemetry, and audit visibility remain readable throughout.
- Recovery and rollback procedures return the workflow to a safe state.
- Operator intervention points are clear and auditable.

## Telemetry review procedures
- Review the dry-run execution summary before starting the scenario.
- Verify RFQ lifecycle state, queue health, worker heartbeats, retry counts, and dead-letter visibility during the run.
- Check for unexpected warnings, stale metrics, or missing snapshots.
- Compare the post-rehearsal telemetry snapshot against the starting snapshot.

## Audit review procedures
- Confirm the rehearsal start, stage transitions, approvals, recoveries, and termination events are captured.
- Confirm proof artifacts and lock references are retained.
- Verify that the audit trail clearly labels rehearsals as simulated or staged.
- Review any operator intervention for completeness and accountability.

## Recovery-time expectations
- Recovery from a staged extraction or pricing failure should be measured in minutes, not hours.
- Worker crash recovery should surface quickly enough for operator intervention.
- Queue congestion should remain bounded and observable without losing workflow context.
- Telemetry outages should trigger immediate pause or escalation rather than continued execution.

## Cadence
- Start with manual rehearsals at low frequency.
- Increase cadence only after telemetry, rollback, and escalation behavior are stable.
- Avoid concurrent rehearsals until the operator review loop has proven reliable.

## Concurrency limits
- Keep concurrency low for initial rehearsals.
- Prefer single-scenario execution or a very small staged batch.
- Increase only when queue visibility and worker recovery remain stable.

## Worker limits
- Use one backend worker and, if needed, one operations-oriented worker for early rehearsals.
- Do not scale workers until queue, telemetry, and rollback behavior are proven.

## RFQ volume limits
- Begin with one RFQ or a very small batch.
- Expand only after the normal and failure-path rehearsals are stable.
- Keep the volume small enough that an operator can review each item manually.

## Safest progression model toward pilot operations
1. Validate normal dry-run processing.
2. Validate failure recovery and rollback drills.
3. Validate queue, worker, and telemetry outage handling.
4. Validate shadow-mode rehearsal outputs and operator approvals.
5. Expand to a small controlled pilot only after all rehearsals remain stable.

## Criteria required before any live submission pilot
- Submission locks, go-live guards, and dry-run protections remain enforced.
- No unresolved queue, telemetry, or worker stability issues remain.
- Shadow-mode rehearsal outputs are consistent and auditable.
- Operator review and escalation procedures are proven and documented.
- The pilot remains isolated from production credentials and live portal endpoints.

## Constraint
This program is documentation only. It does not change orchestration, runtime behavior, or submission authority.
