# Observability Monitoring Baseline

## Purpose

This layer provides operational visibility for LMCP AutoQuote without mutating workflow state, changing procurement behavior, or introducing autonomous execution.

## Architecture

- `app.monitoring.health_service` exposes component and system health summaries.
- `app.monitoring.runtime_diagnostics` inspects runtime directories, DB files, disk pressure, and JSONL integrity.
- `app.monitoring.metrics_service` tracks lightweight in-memory counters for operational events.
- `app.monitoring.workflow_monitor` summarizes workflow stages and detects stalled or invalid workflows.
- `app.monitoring.reporting_service` assembles JSON-safe and human-readable operational summaries.

## Health Model

Health is descriptive only.

- Runtime mode and production mode are reported.
- DB availability is reported as a status signal.
- Workflow engine, audit service, router registry, and persistence health are surfaced separately.
- No health check changes workflow behavior.

## Workflow Monitoring

The monitor can:

- summarize current workflow stages
- count refusals and pending approvals
- detect workflows stalled in active stages
- flag invalid workflow histories

It does not advance, refuse, archive, or otherwise control workflows.

## Metrics Philosophy

Operational counters are local, lightweight, and in-memory.

Tracked counts include:

- RFQs discovered
- RFQs evaluated
- RFQs refused
- quote packs generated
- approvals recorded
- reviews recorded
- proofs recorded
- archived workflows
- workflow failures
- persistence failures
- audit failures

Metrics are informative only and do not gate execution.

## Append-Only Operational Philosophy

- JSONL logs remain in place.
- SQLite-backed durability is additive.
- No mutable audit history is introduced.
- No destructive cleanup is performed by monitoring.

## Persistence Health Policy

- Database availability is reported, not enforced.
- Read/write failures are counted but do not stop manual-production operation.
- JSONL remains the fallback operational source.

## Manual-Production Observability

Observability respects manual-production governance:

- offline operation remains supported
- human approval remains authoritative
- no autonomous final submission is enabled

## Fallback Behavior

If DB access is unavailable:

- monitoring reports degradation
- JSONL compatibility remains active
- workflow execution continues in manual-production mode

## Future PostgreSQL Migration Guidance

The current durability layer is SQLite-first and local-safe for local bootstrap and recovery.

When migration is needed:

- keep JSONL compatibility during the transition
- introduce a repository adapter, not a business-logic rewrite
- preserve append-only semantics
- migrate monitoring independently of workflow behavior

## Rule

Monitoring must never control workflows.
