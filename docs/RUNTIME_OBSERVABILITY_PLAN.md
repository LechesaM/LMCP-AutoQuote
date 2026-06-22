# Runtime Observability Plan

Date: 2026-06-22
Scope: Phase 3 hardening for runtime observability and operational visibility

## Purpose

This plan documents the current observability surface, the gaps that remain, and the minimum telemetry needed for production readiness.

This is documentation only. No runtime behavior changes are proposed here.

## Current Logging Locations

Logging is currently distributed across the runtime rather than centralized into a single observability layer. The main visible logging locations are:

- `app/main.py` and archived startup variants
- `app/tasks.py`
- `app/harvester.py`
- `app/services/tender_harvester.py`
- `app/db/session.py`
- `app/autonomous_engine.py`
- dashboard services under `app/dashboard/*`
- submission and proof services under `app/services/*`
- various backup and frozen runtime files that still contain historical logging patterns

In practice, this means startup, API, harvesting, workflow, DB, dashboard, and submission events are logged in different styles and at different levels of detail.

## Celery Visibility Gaps

Current task modules emit log messages, but the runtime still lacks a clean operational view of Celery activity.

Observed gaps:

- no unified worker heartbeat endpoint
- no consistent task lifecycle event stream
- no standard task correlation between queue event, worker event, and RFQ/work item
- no explicit visibility into retries, backoff, dead-letter-like failure handling, or stuck jobs
- no dashboard summary for worker liveness, task age, or task backlog by queue

## Queue Visibility Gaps

Queue visibility is currently approximated through workflow state and dashboard summaries.

Observed gaps:

- queue overview is built from workflow state, not from broker/worker queue depth
- no explicit queue depth metrics by Celery queue name
- no visibility into age of oldest queued item
- no distinction between logical workflow queues and transport-level queues
- no clear separation between pending approval, review-ready, proof-capture, and actual execution backlog

## Worker Health Gaps

Current runtime health checks are service-level and do not fully describe worker health.

Observed gaps:

- no worker heartbeat freshness signal
- no worker process uptime visibility
- no worker restart/crash count visibility
- no visibility into hung tasks or long-running tasks
- no standard operational signal for "workers alive but not progressing"

## DB Lifecycle Visibility Gaps

Database connectivity is tested, but lifecycle visibility remains shallow.

Observed gaps:

- connection success is logged, but session lifecycle metrics are not surfaced
- no pool utilization visibility
- no transaction duration or slow-query visibility
- no per-request or per-workflow persistence trace
- no visible correlation between DB writes and RFQ/workflow state transitions

## Missing Audit Surfaces

Audit evidence exists in several places, but it is fragmented.

Observed gaps:

- audit events are not consistently emitted for all workflow transitions
- some evidence is JSONL-based, some is file-based, and some is stored in database tables
- no unified audit timeline across acquisition, intelligence, commercial, and submission flows
- no guaranteed operator-facing audit trail for "why" a workflow moved stages
- no explicit audit visibility for retries, overrides, manual approvals, or submission decisions

## Recommended Structured Logging Strategy

Move toward structured JSON logging with a small, stable event schema.

Recommended fields:

- `timestamp`
- `level`
- `service`
- `component`
- `event_type`
- `message`
- `request_id`
- `trace_id`
- `rfq_id`
- `tender_id`
- `workflow_stage`
- `task_id`
- `queue_name`
- `worker_id`
- `environment`
- `status`
- `duration_ms`
- `error_type`
- `error_message`

Policy:

- keep free-text messages for human readability
- ensure the structured fields are always present when known
- emit one event per meaningful state transition rather than logging every internal helper step

## Request Correlation IDs

The runtime should standardize a correlation ID strategy across HTTP, workflow, and task boundaries.

Recommended identifiers:

- `request_id` for inbound HTTP requests
- `trace_id` for end-to-end workflow correlation
- `rfq_id` and/or `tender_id` for business identity
- `task_id` for Celery task execution identity

Recommended propagation:

- generate a request identifier at ingress if none exists
- carry the identifier into workflow state, task payloads, and log records
- preserve the same identifier through dashboard, audit, and submission events where feasible

## RFQ Lifecycle Tracing

The system needs a single traceable story for each RFQ.

Recommended lifecycle checkpoints:

- acquired
- normalized
- extracted
- validated
- priced
- reviewed
- approved
- scheduled
- submitted
- proof captured
- archived or failed

Each checkpoint should emit:

- stage name
- previous stage
- next stage
- actor or worker identity
- decision reason
- timestamp
- correlation IDs

## Worker Heartbeat Strategy

Worker visibility should be explicit rather than inferred.

Recommended heartbeat signals:

- periodic worker heartbeat record
- worker last-seen timestamp
- worker queue membership
- worker task-in-progress count
- worker last task outcome
- worker health status (`healthy`, `degraded`, `stalled`, `offline`)

Recommended operational rule:

- a worker that is alive but not heartbeating within the expected window is treated as degraded
- a worker with repeated task failures is treated as degraded even if process liveness is positive

## Dashboard Health Metrics

The dashboard should expose a compact set of production health metrics.

Recommended dashboard metrics:

- backend API status
- DB connection status
- Celery worker liveness
- Celery backlog by queue
- oldest queued task age
- RFQ stage counts
- failed workflow count
- retry count
- audit write health
- proof capture health
- runtime directory health
- environment name
- last successful refresh timestamp

## Minimum Operational Telemetry for Production Readiness

To consider runtime operations production-ready, the system should expose at minimum:

- request-level access and error logs
- structured workflow transition logs
- worker heartbeat status
- queue backlog visibility
- DB connectivity and basic lifecycle health
- audit write confirmation
- proof capture confirmation
- environment/runtime metadata
- failed-task visibility with retry reason
- stage-level RFQ counts and age distribution

## Recommended Implementation Order

1. Standardize structured logging for new events while preserving existing log output.
2. Add request correlation IDs to HTTP and workflow surfaces.
3. Add worker heartbeat reporting.
4. Add queue depth and task-age visibility.
5. Add stage transition tracing for RFQ lifecycle events.
6. Add dashboard panels for the operational metrics above.

## Non-Goals

- no business feature changes
- no workflow redesign
- no service extraction
- no queue topology rewrite
- no schema migration in this phase

