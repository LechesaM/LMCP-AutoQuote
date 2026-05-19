# Deployment Hardening Baseline

## Purpose

This baseline defines how LMCP AutoQuote is started, validated, backed up, recovered, and shut down in a controlled manual-production deployment.

## Startup Sequence

1. Resolve runtime paths and environment.
2. Validate environment consistency.
3. Validate startup prerequisites.
4. Initialize persistence and operational services.
5. Confirm router registry integrity.
6. Continue only when startup is healthy or explicitly allowed to continue in degraded mode.

## Runtime Integrity Checks

- Workflow JSONL integrity
- SQLite integrity
- Audit file integrity
- Directory consistency
- Orphaned workflow detection
- Corrupted state detection

## Backup Procedures

- Create local timestamped backups under `runtime/backups/`
- Include SQLite, JSONL, and metadata snapshots
- Verify the backup before using it for recovery

## Recovery Procedures

- Validate the backup first
- Require explicit confirmation before restore
- Restore only from a validated backup
- Preserve append-only operational history where possible

## Degraded Startup Handling

- Degraded startup remains supported when already allowed by runtime governance
- Fatal deployment issues must still be surfaced
- Operators must record and investigate degraded startup conditions

## Rollback Guidance

- Prefer restore-from-backup over manual history editing
- Do not mutate workflow history to "fix" a deployment issue
- Refuse or archive impacted work if recovery cannot be made safe

## Governance Rule

Manual-production governance remains authoritative. Deployment hardening must not alter procurement execution behavior or enable autonomous submission.

