# Governance Extraction Phase 2 Report

Date: 2026-06-22
Scope: first real governance code extraction into `lmcp-core/services/governance/`

## Objective

Perform the first low-risk code relocation into `lmcp-core` without changing:

- backend entrypoint authority
- API routes
- runtime behavior
- business workflow ownership

## Files Moved

The following isolated governance utility implementations were relocated into `lmcp-core/services/governance/`:

- `app/monitoring/health_service.py` implementation moved to `lmcp-core/services/governance/health_service.py`
- `app/monitoring/runtime_diagnostics.py` implementation moved to `lmcp-core/services/governance/runtime_diagnostics.py`
- `app/monitoring/metrics_service.py` implementation moved to `lmcp-core/services/governance/metrics_service.py`

## Compatibility Shims Added

The original import paths were preserved by converting the original `app/monitoring/*` modules into thin compatibility wrappers that dynamically load the relocated implementation files:

- `app/monitoring/health_service.py`
- `app/monitoring/runtime_diagnostics.py`
- `app/monitoring/metrics_service.py`

## Imports Preserved

Existing imports continue to work unchanged, including:

- `from app.monitoring.health_service import get_system_health`
- `from app.monitoring.runtime_diagnostics import get_runtime_diagnostics`
- `from app.monitoring.metrics_service import reset_test_metrics, increment_metric, get_metrics_snapshot`

No API module, router, or test import path was changed.

## Why These Utilities Were Chosen

These utilities were selected because they are governance-owned helpers with narrow responsibilities:

- system health formatting and component aggregation
- runtime directory diagnostics
- in-process runtime metric counting and snapshot formatting

They do not own acquisition, intelligence, commercial, or submission workflows.

## Remaining Coupling Risks

The extracted utilities still depend on active runtime modules and are not yet standalone platform services.

Key remaining risks:

- `health_service` still depends on `app.config`, router registry, workflow state, persistence health, and audit service modules
- `runtime_diagnostics` still depends on active runtime path resolution from `app.core.runtime_paths`
- `metrics_service` remains process-local state and does not yet provide shared-worker or persistent metric semantics
- the `lmcp-core` directory is a filesystem destination, not a normal Python package import path, so wrappers are still required
- monitoring, telemetry, and lifecycle orchestration remain in the active runtime tree

## What Was Intentionally Not Moved

The following were intentionally left in place because they remain more tightly coupled:

- `app/monitoring/reporting_service.py`
- `app/monitoring/workflow_monitor.py`
- governance APIs under `app/api/*`
- audit trail services
- control-state, lock, and operator-auth services

For this second extraction step, `app/monitoring/reporting_service.py` was reviewed and intentionally left in place because its runtime-summary surface is broader and its dependency footprint is larger than `metrics_service`, even though it remains governance-oriented.

## Rollback Instructions

To roll back this extraction safely:

1. Restore the original implementation code into:
   - `app/monitoring/health_service.py`
   - `app/monitoring/runtime_diagnostics.py`
   - `app/monitoring/metrics_service.py`
2. Remove the relocated implementation files:
   - `lmcp-core/services/governance/health_service.py`
   - `lmcp-core/services/governance/runtime_diagnostics.py`
   - `lmcp-core/services/governance/metrics_service.py`
3. Remove this report if the extraction is being fully reverted:
   - `docs/GOVERNANCE_EXTRACTION_PHASE2_REPORT.md`

No import call sites, routes, or worker entrypoints need to be reverted because they were not changed.
