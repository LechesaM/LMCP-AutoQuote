# Operational Visibility Surfaces Report

## Scope
Read-only staging visibility surfaces were added to the LMCP Command Centre so operators can see dry-run execution status, RFQ lifecycle state, queue health, worker heartbeats, retry counts, dead-letter visibility, submission lock status, and telemetry health without exposing any submission controls.

## Backend surface
- Added `GET /rfq-lifecycle/upload-dry-run/status` to expose the latest dry-run upload summary.
- The endpoint is read-only and returns the existing dry-run status artifact from `app.services.upload_dry_run_service`.
- No submission execution path was added or modified.

## Frontend surface
- Expanded the dashboard landing page into a command-centre style visibility view.
- Added staging-only panels for:
  - dry-run execution status
  - RFQ lifecycle state counts and recent RFQs
  - queue health
  - worker heartbeats
  - retry and dead-letter visibility
  - submission lock status
  - telemetry health and warnings
- The page remains read-only. No live submission controls are exposed.

## Safety constraints preserved
- Live submission is still blocked by the existing lifecycle guard.
- Dry-run protections remain enabled.
- Production credentials are not displayed.
- No irreversible actions were introduced.

## Verification
- `python3 -m py_compile app/api/rfq_lifecycle_api.py tests/test_rfq_lifecycle_upload_dry_run_status.py tests/test_main_runtime_surface.py`
- `/Users/cash/Documents/.venv/bin/python -m pytest tests/test_main_health_status_routes.py tests/test_main_runtime_surface.py tests/test_rfq_lifecycle_upload_dry_run_status.py`
- `npm run build` in `etenders_acquisition/lmcp-dashboard`
- `python3 scripts/run_dry_run_validation.py`

## Notes
- The staging panels intentionally consume existing read-only telemetry and guard endpoints.
- The command centre is designed to surface operational risk, not to operate the workflow.
