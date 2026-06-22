# Governance Migration Report

Date: 2026-06-22
Scope: first controlled governance extraction into `lmcp-core/services/governance/`

## Objective

Create the initial `lmcp-core` governance landing zone without breaking:

- `app.main:app`
- `/health`
- `/status`
- existing backend imports
- existing router registration
- current worker startup

## What Was Migrated

The migration was deliberately limited to governance-owned documentation and target scaffolding:

- updated `lmcp-core/services/governance/README.md`
- created `lmcp-core/services/governance/docs/README.md`
- created `lmcp-core/services/governance/docs/SOURCE_MAP.md`
- created `lmcp-core/services/governance/runtime/README.md`

This establishes the target boundary for:

- health and status ownership
- audit and operational supervision
- locks and go-live controls
- watchdog and retry oversight
- environment and runtime metadata

## What Was Intentionally Not Migrated

No live Python runtime modules were moved in this first step.

The following remain in place by design:

- `app/main.py`
- `app/monitoring/*`
- governance-related modules under `app/services/*`
- governance-related API routers under `app/api/*`
- runtime JSON files under `runtime/*`
- SQLite or manual-production governance stores

These files are still coupled to the active runtime through direct imports, router registration, runtime paths, and operational scripts.

## Why the Migration Was Kept Narrow

The current governance surface is not isolated enough for source relocation yet.

Primary blockers:

- `/health` and `/status` are owned by the official backend entrypoint in `app/main.py`
- telemetry and observability routes remain registered from the active API tree
- lock, control-state, and audit services still read legacy runtime files directly
- retry supervision spans governance and submission responsibilities
- operator supervision and control state remain mixed across SQLite, JSON, and in-process services

## Remaining Coupling Risks

The main coupling risks that still block direct code movement are:

- health/status logic is split between `app/main.py` and `app/monitoring/*`
- governance APIs are wired through the shared router registry in `app/api/router_registry.py`
- `system_control_service`, `system_state_service`, and lock services depend on legacy runtime file locations
- audit responsibilities are split across SQLAlchemy models, JSON artifacts, and manual-production stores
- retry supervision overlaps with submission execution and Celery scheduling

## Future Extraction Recommendations

Recommended governance extraction order:

1. Extract governance-owned documentation, config contracts, and runtime path definitions first.
2. Extract pure read-only monitoring helpers that do not own business orchestration.
3. Extract control-state adapters behind compatibility wrappers while keeping legacy file paths active.
4. Extract audit and supervision services after persistence ownership is clarified.
5. Extract governance API routers last, after imports can be redirected safely.

Modules that should wait:

- `app/services/submission_retry_service.py`
- `app/services/retry_engine_service.py`
- `app/services/operator_auth_service.py`
- `app/api/telemetry_routes.py`
- `app/api/operator_auth_api.py`

## Rollback Instructions

This migration is documentation-only and can be rolled back without runtime impact by removing:

- `lmcp-core/services/governance/docs/README.md`
- `lmcp-core/services/governance/docs/SOURCE_MAP.md`
- `lmcp-core/services/governance/runtime/README.md`
- the updated content in `lmcp-core/services/governance/README.md`
- `docs/GOVERNANCE_MIGRATION_REPORT.md`

No backend imports, runtime files, routes, worker entrypoints, or compose files were changed in this step.

## Verification

Expected verification for this step:

- backend entrypoint remains `app.main:app`
- `/health` remains available
- `/status` remains available
- `pytest tests/test_main_health_status_routes.py` passes
- `pytest tests/test_main_runtime_surface.py` passes
