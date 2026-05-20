# Day 1 Burn-In Checklist

Status target: supervised-live burn-in only.

## Runtime
- Confirm backend API is healthy.
- Confirm frontend loads on the current supervised-live port.
- Confirm no critical runtime alerts are unresolved.
- Confirm degraded-state banners appear only when data is stale or fallback is active.
- Confirm queue lag is visible and stable.

## Governance
- Confirm proof capture remains mandatory.
- Confirm `review_ready` remains mandatory.
- Confirm final submission remains manual-only.
- Confirm operator attribution is present on actions.
- Confirm audit continuity is intact.

## Stability
- Confirm no duplicate routes are reported.
- Confirm auth and RBAC remain active.
- Confirm persistence health is healthy or clearly degraded with operator-visible warnings.
- Confirm telemetry and observability routes return JSON-safe responses.
- Confirm no autonomous actions are introduced.

## Notes
- Burn-in is observational and does not change workflow policy.
- Any blocker must be recorded in the Day 1 burn-in report.
