# Production Persistence Hardening

## Overview
LMCP persistence is hardened for supervised-live production with SQLite fallback, PostgreSQL-ready configuration, Redis-ready queue durability, backup automation, restore validation, and read-only persistence operations.

## SQLite vs PostgreSQL
- SQLite remains the safe fallback for local and supervised-live recovery scenarios.
- PostgreSQL is the preferred production backend when configured.
- Production and supervised-live deployments emit warnings when SQLite is used.

## Redis Queue Readiness
- Queue backend selection is explicit.
- Local queue support remains available for fallback and development.
- Redis configuration is advisory/readiness-only until enabled through deployment profiles and environment variables.

## Backup Validation
- Backups are timestamped and manifest-backed.
- Backup age is reported and warning thresholds are advisory.
- Manual backup triggers remain explicit and auditable.

## Restore Validation
- Restore validation is non-destructive.
- Manifest checks, file checks, and read-only persistence checks are required.
- Validation does not mutate runtime data.

## DLQ Behavior
- Failed jobs move to the dead-letter queue when retry eligibility is exhausted.
- Retry and archive actions require explicit confirmation.
- No automatic retry loop can bypass operator review.

## Worker Supervision
- Worker heartbeats are tracked for stale-worker detection.
- Queue recovery services provide recommendations only.
- No autonomous remediation is introduced.
