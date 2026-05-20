# Operator Launch Protocol

This protocol describes the operator-facing launch sequence for supervised-live production usage.

## Before Login

- Confirm deployment status is approved.
- Confirm the UI is showing the expected cutover environment.
- Confirm any active degraded-mode banners are understood.

## Login Steps

1. Sign in with a governed role.
2. Confirm session freshness and API health.
3. Confirm the dashboard shows live or safe fallback telemetry.
4. Confirm there are no unresolved critical blockers.

## Operator Checks After Login

- Review queue visibility.
- Telemetry freshness.
- Startup validation panel.
- Governance status.
- Runtime safety banner state.
- Backup and restore readiness.

## Launch Discipline

- Treat degraded mode as visible, not hidden.
- Escalate any stale telemetry or session-expiry warnings immediately.
- Keep manual approval and proof capture in the operator loop.

## Stop Conditions

- auth failure
- expired session
- stale telemetry with critical blockers
- queue/persistence failure
- governance inconsistency

The operator must stop and escalate rather than attempt autonomous remediation.
