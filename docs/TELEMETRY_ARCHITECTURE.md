# Telemetry Architecture

Date: 2026-06-22
Scope: Phase 3 runtime telemetry and operational diagnostics foundation

## Purpose

This document defines the telemetry model for LMCP AutoQuote so that runtime operations can be observed consistently across HTTP requests, Celery tasks, workflow state, and audit events.

This is documentation only. No runtime behavior changes are proposed here.

## Design Goals

- make operational state visible without reading raw runtime files
- correlate HTTP requests, Celery tasks, workflow transitions, and audit events
- separate business telemetry from infrastructure telemetry
- expose enough signal to detect stalls, regressions, queue buildup, and workflow failures
- keep the telemetry schema stable and minimal

## Structured Logging Format

Telemetry logs should be emitted as structured events with a consistent schema.

Recommended core fields:

- `timestamp`
- `level`
- `service`
- `component`
- `event_type`
- `message`
- `environment`
- `request_id`
- `trace_id`
- `rfq_id`
- `tender_id`
- `workflow_stage`
- `task_id`
- `queue_name`
- `worker_id`
- `status`
- `duration_ms`
- `error_type`
- `error_message`
- `metadata`

Recommended rules:

- `message` stays human-readable
- `metadata` may contain component-specific detail
- IDs should be included whenever known, not only on errors
- one event should represent one meaningful state transition or diagnostic checkpoint

## RFQ Correlation IDs

LMCP should use a stable business correlation model.

Recommended identifiers:

- `rfq_id` for RFQ-level business identity
- `tender_id` for tender/workspace identity
- `request_id` for inbound HTTP identity
- `trace_id` for end-to-end workflow correlation
- `task_id` for Celery execution identity

Recommended propagation:

- generate `request_id` at request ingress if none exists
- derive or attach a `trace_id` when an RFQ enters the workflow
- carry `rfq_id`, `tender_id`, and `trace_id` through task payloads and workflow records
- preserve the same correlation values in logs, audit events, and dashboard summaries

## Request Tracing

Request tracing should show the path from HTTP ingress to workflow side effects.

Recommended trace checkpoints:

- request received
- request validated
- workflow lookup performed
- workflow state loaded
- action dispatched
- DB write attempted
- audit record written
- response returned

Recommended trace fields:

- request path
- request method
- status code
- elapsed time
- actor or session identity if known
- correlation IDs
- outcome classification

## Celery Task Tracing

Celery task events need to be visible as first-class operational telemetry.

Recommended task lifecycle events:

- task queued
- task started
- task heartbeat
- task progress
- task retry
- task failed
- task succeeded
- task dead-lettered or permanently abandoned

Recommended task fields:

- `task_id`
- `task_name`
- `queue_name`
- `worker_id`
- `retries`
- `routing_key`
- `correlation_id`
- `rfq_id`
- `tender_id`
- `status`
- `duration_ms`
- `failure_class`

## Worker Heartbeat Events

Workers should emit explicit heartbeat telemetry.

Recommended heartbeat payload:

- `worker_id`
- `hostname`
- `process_id`
- `queue_names`
- `last_seen_at`
- `active_task_count`
- `uptime_seconds`
- `health_status`
- `environment`

Heartbeat interpretation:

- `healthy` means the worker is processing and heartbeating normally
- `degraded` means the worker is alive but lagging or failing tasks
- `stalled` means the worker is alive but not making progress
- `offline` means the worker is not reporting within the expected window

## Queue Telemetry

Queue telemetry should distinguish transport queues from workflow queues.

Recommended queue metrics:

- queue depth
- oldest task age
- tasks started per interval
- tasks completed per interval
- retries per interval
- failures per interval
- dead-letter counts

Recommended queue dimensions:

- `queue_name`
- `environment`
- `service`
- `task_name`
- `failure_class`

## Submission Audit Telemetry

Submission actions require stronger visibility than ordinary workflow logs.

Recommended submission audit events:

- proof capture started
- proof capture completed
- submission pack created
- submission validation passed
- submission validation failed
- submission approved
- submission scheduled
- submission executed
- submission receipt captured
- submission retry requested
- submission retry completed
- submission permanently failed

Recommended audit fields:

- `rfq_id`
- `tender_id`
- `submission_method`
- `submission_channel`
- `portal_name`
- `actor`
- `decision`
- `reason`
- `proof_path`
- `receipt_path`
- `timestamp`

## Frontend Operational Telemetry

The frontend should surface operational state rather than raw internals.

Recommended frontend telemetry surfaces:

- backend API status
- DB status
- worker status
- queue backlog
- oldest queued item age
- RFQ stage counts
- failed workflow counts
- submission proof status
- environment name
- last refresh time

Frontend telemetry should remain compact and operator-friendly.

## Runtime Metrics Surfaces

The runtime should expose a small set of stable metrics views.

Recommended surfaces:

- `/health` for overall liveness
- `/status` for backend, DB, broker, environment, and timestamp
- workflow dashboard summaries
- queue dashboards
- worker dashboards
- audit summary views
- submission/proof views

## Operational Event Categories

Telemetry should be categorized by service boundary.

### Acquisition

Events related to source discovery, harvesting, source health, retries, document fetching, and portal discovery.

### Intelligence

Events related to document normalization, extraction, BOQ parsing, OCR, validation, and classification.

### Commercial

Events related to pricing, profitability, adjudication, supplier scoring, quote compilation, and approval/review decisions.

### Submission

Events related to submission pack creation, proof generation, portal/email execution, retry handling, and receipt capture.

### Governance

Events related to health, status, runtime diagnostics, audit, locks, supervision, and operational control.

## Failure Classification Taxonomy

Failures should be classified consistently so that alerting and dashboards can group them.

Recommended classes:

- `transient_network`
- `broker_unavailable`
- `database_unavailable`
- `filesystem_unavailable`
- `portal_change`
- `portal_auth_failure`
- `validation_failure`
- `extraction_failure`
- `pricing_failure`
- `submission_failure`
- `workflow_lock_failure`
- `audit_failure`
- `timeout`
- `rate_limited`
- `unknown`

Recommended severity:

- `info` for normal lifecycle events
- `warning` for recoverable failures and retries
- `error` for operation failures that require attention
- `critical` for system-wide degradation or loss of core workflow capability

## Log Aggregation Strategy

Recommended approach:

- aggregate structured logs centrally
- preserve raw logs for forensic review
- index by `environment`, `service`, `rfq_id`, `tender_id`, `task_id`, and `failure_class`
- keep a short retention hot tier for rapid search and a longer cold tier for audit evidence

The stack itself is not mandated here, but the architecture should support:

- searchable JSON logs
- cross-service correlation
- long-retention audit access

## Metrics Collection Strategy

Recommended approach:

- expose a small set of counters, gauges, and histograms
- collect worker, queue, DB, and API metrics separately
- use workflow-stage counts and latency histograms for business visibility
- keep metrics cardinality under control by limiting labels to stable identifiers

Suggested metric families:

- HTTP request count and latency
- Celery task count, latency, retry count, failure count
- queue depth and oldest age
- worker heartbeat freshness
- DB connection health
- audit write success/failure
- submission/proof completion counts

## Dashboard Telemetry Surfaces

Recommended dashboard sections:

- runtime health summary
- worker and queue status
- RFQ lifecycle stage counts
- pending approval / review / proof capture queues
- failed and retrying tasks
- submission proof status
- recent audit events
- environment and deployment metadata

## Alerting Strategy

Alerts should be tied to operational impact rather than individual log lines.

Recommended alert triggers:

- backend health failure
- DB connectivity failure
- worker heartbeat stale
- queue backlog above threshold
- oldest task age above threshold
- submission proof generation failure rate elevated
- repeated workflow lock or audit failures
- repeated portal or broker failures

Alert routing should distinguish:

- immediate outage conditions
- degraded-but-operational conditions
- investigation-only warnings

## Dead-Letter Handling Visibility

Dead-letter handling should be visible even if the broker implementation changes later.

Recommended visibility:

- permanent failure count
- dead-letter queue depth if present
- retry exhaustion events
- failure reason classification
- final disposition for abandoned tasks

## Minimum Telemetry for Production Readiness

The minimum telemetry surface for production readiness is:

- structured request and workflow logs
- request correlation IDs
- Celery task tracing
- worker heartbeat visibility
- queue depth and age telemetry
- DB health visibility
- audit event visibility
- submission proof telemetry
- frontend operational summary
- failure classification

## Recommended Future Observability Stack

The future stack should provide:

- centralized structured log aggregation
- metrics collection and alerting
- dashboard panels for operations and workflow health
- trace-like correlation across HTTP and Celery
- long-retention audit evidence storage

The exact vendor/tool choice can be deferred, but the runtime should be designed so that adopting a standard stack later does not require changing business workflows.

