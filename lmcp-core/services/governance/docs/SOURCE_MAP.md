# Governance Source Map

This source map identifies the current runtime assets that belong logically to the Governance Service boundary.

## Health and Status

- `app/main.py`
- `app/monitoring/health_service.py`
- `app/monitoring/runtime_diagnostics.py`
- `app/services/portal_health_dashboard.py`
- `app/services/etenders_status_enumerator_v50_8_4_service.py`

## Audit and Supervision

- `app/services/audit_trail_service.py`
- `app/services/external_audit_export_service.py`
- `app/services/system_control_service.py`
- `app/services/system_state_service.py`
- `app/services/operator_auth_service.py`

## Guards and Locks

- `app/services/production_lock_service.py`
- `app/services/immutable_submission_lock_service.py`
- `app/services/go_live_guard_service.py`
- `app/services/security_guard_service.py`
- `app/services/disk_safety_guard.py`

## Monitoring and Retry Oversight

- `app/monitoring/workflow_monitor.py`
- `app/monitoring/metrics_service.py`
- `app/monitoring/reporting_service.py`
- `app/services/submission_retry_service.py`
- `app/services/retry_engine_service.py`

## Governance-Adjacent API Surfaces

These remain in the runtime API tree and are not migrated in this step:

- `app/api/audit_trail_api.py`
- `app/api/go_live_guard_api.py`
- `app/api/production_lock_api.py`
- `app/api/system_control.py`
- `app/api/operator_auth_api.py`
- `app/api/telemetry_routes.py`
- `app/api/live_telemetry_adapters.py`
- `app/api/telemetry_contracts.py`
