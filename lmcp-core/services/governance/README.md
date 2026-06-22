# Governance Service

`lmcp-core/services/governance/` is the target home for runtime supervision, control-state enforcement, auditability, and operational safety in LMCP.

## Ownership

This service boundary owns:

- API liveness and runtime status semantics
- production locks and go-live guardrails
- operator authentication and supervision controls
- audit trail and external audit export responsibilities
- watchdog, runtime diagnostics, telemetry health, and retry supervision policy
- environment and runtime metadata that describe how the platform is operating

## Current Runtime Sources

The active governance runtime still lives in the existing backend tree. The current source modules are primarily:

- `app/main.py`
- `app/monitoring/health_service.py`
- `app/monitoring/runtime_diagnostics.py`
- `app/monitoring/workflow_monitor.py`
- `app/monitoring/metrics_service.py`
- `app/services/audit_trail_service.py`
- `app/services/external_audit_export_service.py`
- `app/services/production_lock_service.py`
- `app/services/go_live_guard_service.py`
- `app/services/system_control_service.py`
- `app/services/system_state_service.py`
- `app/services/operator_auth_service.py`
- `app/services/security_guard_service.py`
- `app/services/disk_safety_guard.py`
- `app/services/submission_retry_service.py`
- `app/services/retry_engine_service.py`

## Migration Posture

This first migration does not move live Python runtime modules. It establishes the target governance boundary and centralizes migration documentation under this folder while leaving:

- `app.main:app` as the official backend entrypoint
- current router registration unchanged
- current imports unchanged
- current Celery ownership unchanged

## Subdirectories

- `docs/`
  - governance-specific migration notes and source maps
- `runtime/`
  - target location for future governance-owned runtime metadata and control-state assets after compatibility work is complete

## Out of Scope

This boundary does not yet absorb:

- acquisition lifecycle orchestration
- pricing/commercial decision logic
- submission execution logic
- any frontend assets
