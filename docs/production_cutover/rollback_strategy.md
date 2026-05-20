# Rollback Strategy

Rollback is designed to restore the last safe, supervised-live known-good state without destructive automation.

## Rollback Triggers

- failed strict startup
- auth/RBAC failure
- router integrity failure
- missing frontend assets
- degraded runtime with critical blockers
- persistence or queue degradation that prevents safe operation

## Rollback Sequence

1. Stop new operator activity.
2. Preserve current logs, snapshots, and audit records.
3. Restore the previous deployment artifact set.
4. Re-validate backend startup.
5. Re-validate auth/RBAC.
6. Re-validate telemetry and runtime resilience.
7. Confirm operators can access the prior stable dashboard.

## Rollback Constraints

- No destructive data deletion.
- No audit chain truncation.
- No silent rollback.
- No automatic cutover back to a newer release without operator review.

## Expected Outcome

Rollback should return the platform to a known-good supervised-live state while preserving governance evidence and operator accountability.
