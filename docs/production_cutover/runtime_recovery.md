# Runtime Recovery

Runtime recovery focuses on preserving operator visibility and the last known safe telemetry during transient failures.

## Recovery Principles

- Preserve last-known-safe telemetry.
- Mark stale telemetry visibly.
- Surface degraded runtime status to operators.
- Avoid silent failures.
- Prefer advisory warnings over hidden fallback.

## Recovery Sources

- runtime metrics snapshot
- health snapshot history
- backup status
- restore readiness
- queue and worker supervision

## Recovery Workflow

1. Detect degradation or stale telemetry.
2. Serve the last known safe snapshot.
3. Mark the data source as degraded or fallback-backed.
4. Emit operator-visible warnings.
5. Retry underlying services using the configured retry policy.
6. Re-validate runtime health before clearing degraded state.

## Recovery Limits

- Recovery is read-only and advisory.
- Recovery must not trigger submission, approval, or workflow transitions.
- Recovery must never suppress critical alerts.
