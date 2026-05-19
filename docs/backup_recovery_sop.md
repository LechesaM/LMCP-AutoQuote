# Backup and Recovery SOP

## Backup Procedure

- Confirm the system is in a stable operational state.
- Run the local backup workflow.
- Verify that the backup contains the database, workflow logs, audit history, and metadata.
- Store the backup in the timestamped `runtime/backups/` location.

## Recovery Procedure

- Validate the backup before restore.
- Obtain explicit operator confirmation before overwriting runtime data.
- Restore the database and JSONL logs from the validated backup.
- Re-run deployment and integrity checks after restore.

## Safety Rules

- Never overwrite runtime data without confirmation.
- Never edit audit history manually.
- Never restore from an unverified backup.

## Manual-Production Guidance

If recovery cannot be completed safely, pause operations, refuse new work, and escalate to the operator lead.

