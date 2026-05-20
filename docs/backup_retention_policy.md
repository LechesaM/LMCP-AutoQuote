# Backup Retention Policy

## Retention Windows
- Audit events: 10 years
- Workflow events: 2 years
- Operator actions: 2 years
- Telemetry snapshots: 90 days
- Runtime logs: 90 days
- Incidents: 10 years
- Backups: 30 days

## Dry-Run Behavior
- Retention runs default to dry-run mode.
- Dry runs report what would be archived or deleted.
- No deletion occurs unless explicit confirmation is provided.

## Archive Strategy
- Archive before deletion where supported.
- Preserve audit and incident records for long-term traceability.

## Governance
- Retention never bypasses manual confirmation.
- No autonomous cleanup is introduced.
