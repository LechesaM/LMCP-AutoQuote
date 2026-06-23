# Orchestration Visibility Plan

## Purpose
Define a safe visibility layer for LMCP orchestration without changing runtime orchestration behavior. This plan maps how RFQ work moves through queues, task chains, retries, recovery paths, and dead-letter handling so operators can see what is happening before any future extraction or refactor.

## Current orchestration flow
The current orchestration surface spans acquisition, intelligence, commercial, submission, and governance boundaries, but most of the runtime control plane still lives in shared queue and workflow helpers.

### RFQ lifecycle transitions
- RFQs enter the system through acquisition and harvest-related workflows.
- Extraction moves RFQs into structured document and BOQ states.
- Commercial processing advances pricing, review, and approval-related states.
- Submission moves approved work through portal automation and receipt capture.
- Governance tracks health, audit, retry, and supervision states across the lifecycle.

### Task chain visibility
- Celery tasks currently provide limited direct visibility into chained work.
- Task start, completion, and retry events should be traceable back to an RFQ correlation identifier.
- Chain boundaries should be visible at the level of acquisition, extraction, pricing, approval, and submission handoff.

### Queue transition visibility
- Queue transitions should show when work moves from pending to running, retry pending, blocked, completed, or failed.
- Operator-facing visibility needs the ability to see queued depth, running items, retry backlog, and blocked work.
- Queue transitions should be distinguishable from workflow state transitions so operators can isolate control-plane issues from business-process issues.

### Retry and recovery visibility
- Retry attempts need to be visible with reason, attempt count, and maximum attempt thresholds.
- Recovery visibility should show when a job is being retried, recovered from a snapshot, or routed to a dead-letter queue.
- Recovery events should expose whether the action is advisory, automatic, or requires human intervention.

### Dead-letter visibility
- Dead-letter records should be visible as a terminal operational artifact, not as an active workflow state.
- Operators should be able to see the source job, failure reason, retry history, and archive status.
- DLQ visibility must make it clear which items are recoverable and which are only retained for audit.

### Orchestration bottlenecks
- Bottlenecks are most likely to appear at queue backlogs, stale workers, retry loops, and blocked operator approvals.
- Hidden bottlenecks can also occur when queue state, workflow state, and filesystem shadow state drift apart.
- Any future visibility surface should flag blocked queues before they turn into submission delays.

### Hidden orchestration coupling
- Queue helpers currently overlap with workflow monitoring and runtime telemetry.
- Some flow visibility is embedded in shared helpers that also serve dashboard and health surfaces.
- This coupling should be treated as a migration risk because queue state, workflow state, and telemetry state are not cleanly separated yet.

### Workflow ownership boundaries
- Acquisition owns discovery and harvest initiation.
- Intelligence owns document parsing and extraction.
- Commercial owns pricing and approval logic.
- Submission owns portal automation and proof capture.
- Governance owns health, supervision, telemetry, retry, and recovery controls.
- Unified command centre surfaces should aggregate these boundaries without owning workflow execution.

## Orchestration tracing model

### Orchestration tracing events
The recommended event categories are:
- `rfq_discovered`
- `rfq_extracted`
- `rfq_priced`
- `rfq_reviewed`
- `rfq_approved`
- `submission_prepared`
- `submission_sent`
- `receipt_captured`
- `retry_scheduled`
- `retry_executed`
- `dead_lettered`
- `recovered`
- `worker_heartbeat`
- `queue_transition`
- `workflow_state_transition`

### Workflow correlation strategy
- Every orchestration event should carry a stable RFQ or tender correlation identifier.
- Queue job identifiers should be linked to RFQ identifiers and workflow stage identifiers.
- Celery task metadata should carry the same correlation identifier through chains and retries.
- Recovery events should reference both the original job and the recovery action.

### Queue transition telemetry
- Telemetry should expose counts for queued, running, retry pending, blocked, failed, completed, and dead-lettered work.
- Transition telemetry should include before/after state, actor, queue name, and timestamp.
- Queue telemetry should be read-only and must not mutate orchestration state.

### Task dependency telemetry
- Task dependency telemetry should show the upstream task, downstream task, and whether the handoff succeeded.
- Dependency failures should be visible as propagation events rather than silent retries.
- Chained tasks should report the chain root so operators can see where a workflow originated.

### Failure propagation visibility
- Failures should be classified as transient, retryable, blocked, terminal, or operator-action-required.
- A failure should clearly indicate whether it was absorbed by retry logic, diverted to DLQ, or surfaced to an operator.
- Visibility should include the last successful orchestration milestone so operators know how far the workflow progressed.

## Operational surfaces

### Recommended dashboard surfaces
- RFQ lifecycle board
- Queue depth and backlog panel
- Retry and dead-letter panel
- Worker heartbeat and stale-worker panel
- Recovery and intervention panel
- Submission handoff and receipt visibility panel

### Operational intervention points
- Retry a failed orchestration job.
- Requeue a DLQ item after inspection.
- Archive a dead-letter item that is no longer actionable.
- Investigate stale workers or stalled queue transitions.
- Review blocked approval or submission handoffs.

## Safe future extraction sequence
1. Extract read-only orchestration tracing helpers.
2. Extract queue transition telemetry helpers.
3. Extract retry and dead-letter reporting helpers.
4. Extract worker health and recovery reporting helpers.
5. Only then consider any deeper orchestration control-plane refactor.

## Constraints
- Do not change queue semantics.
- Do not change Celery task behavior.
- Do not alter RFQ lifecycle transitions.
- Do not move workflow ownership across services yet.
- Do not make dead-letter handling destructive or auto-purging.

## Outcome
This plan defines the visibility contract needed to harden orchestration safely before any future extraction work.

