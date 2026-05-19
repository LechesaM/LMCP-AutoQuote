# Operator Dashboard Baseline

## Purpose

The operator dashboard provides visibility and manual assistance for LMCP AutoQuote.
It does not create a new automation path and it does not bypass workflow governance.

## Architecture

- `app.dashboard.dashboard_service` aggregates operational and workflow summaries.
- `app.dashboard.workflow_queue_service` exposes queue-oriented views by workflow stage.
- `app.dashboard.health_views` exposes dashboard-friendly health summaries.
- `app.dashboard.report_views` exposes reporting-oriented JSON-safe structures.
- `app.dashboard.operator_actions_service` performs a very small set of safe operator actions.

## Queue Philosophy

Queues are views over persisted workflow state.

- no direct filesystem scanning is used unless a fallback is required by persistence
- queue membership is derived from the workflow engine and repository layer
- queue views are read-only

## Manual-Production Governance

Manual-production remains authoritative.

- approvals still require human action
- review readiness still depends on prior approval
- proof capture still depends on review readiness
- no autonomous final submission is introduced

## Allowed Operator Actions

- archive a workflow
- refuse a workflow
- add an operator note
- acknowledge a warning

These actions must:

- pass through the workflow engine when they mutate workflow state
- emit audit events
- remain safe in offline/manual-production mode

## Prohibited Actions

- autonomous submission
- workflow skipping
- bypassing approvals
- bypassing review state
- bypassing proof capture rules
- bypassing workflow transition rules

## Workflow Queue Definitions

- pending approval queue: `approval_required`
- review-ready queue: `approved`
- proof-capture queue: `review_ready`
- refused queue: `refused`
- archived queue: `archived`

## Health and Reporting

The dashboard surfaces:

- runtime health
- DB health
- persistence health
- audit health
- workflow health
- monitoring health

Reporting structures are JSON-safe and intended for operator visibility only.

## Rule

The dashboard must never bypass workflow controls.
