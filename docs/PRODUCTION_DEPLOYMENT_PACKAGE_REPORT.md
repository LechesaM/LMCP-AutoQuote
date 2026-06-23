# Production Deployment Package Report

This document defines the controlled production deployment packaging governance for repeatable enterprise rollout.

## Package Artifacts
- `docker-compose.production.example.yml`
- `.env.production.example`
- `runtime/production/go_live_guards/submission_locks.json`
- `scripts/validate_production_package.py`

## Production-Safe Defaults
- `LMCP_ALLOW_FINAL_AUTOMATION=false`
- `LMCP_DRY_RUN_MODE=true`
- `LMCP_REQUIRE_HUMAN_SUPERVISION=true`
- `LMCP_PRODUCTION_MODE=locked_production`
- `LMCP_DEPLOYMENT_PROFILE=production`
- `STRICT_PRODUCTION_STARTUP=1`
- `LMCP_ALLOW_DEGRADED_STARTUP=false`
- `LMCP_OBSERVABILITY_ENABLED=1`
- `LMCP_SECRET_KEY=change-me-production-secret`
- `LMCP_CORS_ORIGINS=https://lmcp.example.com`
- `LMCP_OPERATOR_SESSION_COOKIE_SECURE=true`
- `LMCP_OPERATOR_AUTH_ALLOW_DEV_FALLBACK=false`

## Runtime Segmentation
The production package isolates runtime storage under:
- `/app/runtime/production`

The package keeps production runtime paths separate from staging and retains dedicated directories for:
- logs
- audit trails
- proofs
- submission history
- locks
- operator auth
- manual production

The compose template also encodes the production-safe defaults directly so the package remains locked down even before the environment file is adjusted.

## Submission Safety
The production package requires a production submission lock file:
- `/app/runtime/production/go_live_guards/submission_locks.json`

The lock template explicitly disables:
- final automation
- live portal submission
- production credential usage
- submission execution

## Observability and Storage
The production package defines:
- backend
- frontend
- PostgreSQL
- Redis
- workers
- Prometheus
- Grafana

Database and broker are isolated to local compose services and runtime state is separated from staging.

## Credential Safety
Production submission credentials are blank by default in the example package.
Credential material must be supplied only through supervised production secrets management.
Session cookies are secure by default and development auth fallback remains disabled.

## Validation Contract
The production package validator checks:
- example files exist
- dry-run defaults remain safe
- final automation remains disabled
- supervision is mandatory
- credentials are not embedded
- runtime paths are production-separated
- observability services are defined
- database and broker are isolated
- submission lock file is present and locked

## Safety Boundary
This package governs deployment packaging only. It does not:
- enable autonomous live submissions
- weaken supervision boundaries
- redesign orchestration
- grant irreversible execution authority
- replace the institutional governance layers
