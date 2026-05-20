# Deployment Checklist

Use this checklist before any supervised-live cutover.

## Preflight

- Confirm `LMCP_SECRET_KEY` is a real production secret.
- Confirm `STRICT_PRODUCTION_STARTUP=true`.
- Confirm `LMCP_DEPLOYMENT_PROFILE=supervised_live`.
- Confirm `LMCP_AUTH_REQUIRED=1`.
- Confirm `LMCP_AUTH_ALLOW_DEMO_USERS=0`.
- Confirm the database backend is configured for the intended deployment mode.
- Confirm queue backend configuration is available for the target environment.

## Application Readiness

- Validate backend startup health.
- Validate router integrity.
- Validate RBAC initialization.
- Validate telemetry endpoints.
- Validate persistence and queue health.
- Validate backup freshness and restore readiness.
- Confirm frontend build passes.

## Cutover Steps

1. Deploy backend services.
2. Deploy frontend assets.
3. Confirm startup health report is healthy or conditionally healthy with approved warnings.
4. Verify auth, telemetry, operator operations, and governance views are reachable.
5. Verify no dormant overlays or blocked interactions exist in the frontend.
6. Confirm operators can authenticate and view only their permitted sections.

## Go / No-Go

- **GO** only if all critical checks pass.
- **CONDITIONAL_GO** if only non-critical warnings remain and an operator has approved them.
- **BLOCKED** if any critical blocker remains.

## Non-Negotiables

- Manual approval remains mandatory.
- `review_ready` remains mandatory.
- Proof capture remains mandatory.
- Final submission remains manual-only.
