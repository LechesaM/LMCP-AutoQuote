# Retention Enforcement Policy

Retention is enforced in dry-run mode first.

## Retention windows
- Audit events: long retention
- Workflow events: long retention
- Operator actions: long retention
- Telemetry snapshots: limited retention
- Runtime logs: limited retention
- Incidents: long retention
- Backups: short retention with warning thresholds

## Legal holds
- Legal holds override normal retention suggestions.
- Legal holds are registered and released manually.

## Dry-run behavior
- Retention evaluation reports what would be archived or removed.
- No destructive deletion occurs without explicit confirmation.

