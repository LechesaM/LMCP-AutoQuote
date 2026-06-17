# Persistence And Audit Baseline

## Architecture

LMCP AutoQuote now uses a dual persistence model:

- JSONL remains the operational compatibility layer
- SQLite provides additive durability for structured persistence

The local default database lives at `runtime/manual_production/lmcp_operations.db`.

This is intentionally local-file safe and does not require an external database.

## JSONL Compatibility Policy

The following JSONL files remain in place and are not replaced yet:

- `approvals.jsonl`
- `submission_reviews.jsonl`
- `submission_proofs.jsonl`
- `workflow_events.jsonl`
- `workflow_state.jsonl`

JSONL remains authoritative for the current manual-production workflow.
SQLite writes are additive and must never block the manual path.

## Append-Only Audit Philosophy

Audit and workflow records remain append-only.

No destructive migrations are introduced.
No cleanup or deletion semantics are added.
No mutable audit history is permitted.

## Workflow Durability Model

Workflow transitions are written to both:

- the existing JSONL workflow logs
- the SQLite workflow tables

The workflow engine still enforces the same transition rules and manual-production guardrails.

If SQLite is unavailable, the workflow engine continues with JSONL only.

## Manual-Production Offline Safety

Manual-production mode must work fully offline.

The persistence layer is designed so that:

- JSONL writes continue even if SQLite fails
- SQLite initialization failures only produce warnings
- existing services still complete their work without DB availability

## DB Fallback Behavior

SQLite persistence is additive only.

When the DB is unavailable:

- JSONL logging continues
- service behavior does not change
- workflow state lookup falls back to JSONL

## Future PostgreSQL Migration Guidance

The repository and persistence models are structured so that a later PostgreSQL move can reuse:

- typed entities
- repository abstractions
- append-only persistence semantics
- existing workflow and audit contracts

Any later migration should preserve the current JSONL compatibility path until the new durable backend is fully proven.
