# PostgreSQL Migration Plan

## Migration Strategy
1. Back up the current runtime store.
2. Validate backup manifest and restore readiness.
3. Move to PostgreSQL in a staging-first deployment.
4. Validate audit, workflow, queue, and operator-action tables.
5. Switch production only after readiness checks pass.

## Required Checks
- Current SQLite DB path
- PostgreSQL URL and credentials
- Table inventory
- JSONL fallback inventory
- Audit/workflow/operator-action/queue table inventory
- Backup requirement confirmation

## Rollback Plan
- Keep SQLite backup intact until PostgreSQL is verified.
- Roll back to the last known-good backup if validation fails.
- Do not perform destructive migration without explicit operator approval.

## Notes
- Migration is readiness-only in this branch.
- No automatic migration or data loss path is added.
