# Production Runtime Checklist

## Startup validation

- Auth stack loads correctly.
- RBAC permissions are enforced.
- Telemetry endpoints return JSON-safe responses.
- Governance routes remain manual-only.

## Deployment validation

- Docker and nginx configuration are valid.
- Runtime profiles resolve correctly.
- Legacy routers stay disabled by default.

## Daily health checks

- Runtime metrics
- Incident status
- Backup validation
- Queue health
- Source health

