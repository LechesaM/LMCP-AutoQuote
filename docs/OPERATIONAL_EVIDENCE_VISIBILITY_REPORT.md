# Operational Evidence Visibility Report

## Scope
This change exposes controlled operational rehearsal evidence inside the LMCP Command Centre as a read-only surface.

It does not enable live submissions, remove dry-run protections, expose production credentials, or add any irreversible actions.

## Backend Surfaces Added
The following read-only endpoints were added to the RFQ lifecycle router:
- `GET /rfq-lifecycle/rehearsals/history`
- `GET /rfq-lifecycle/rehearsals/latest`
- `GET /rfq-lifecycle/rehearsals/{run_id}`

These endpoints are backed by [`app/services/operational_rehearsal_service.py`](/Users/cash/Documents/app/services/operational_rehearsal_service.py), which scans `runtime/staging/rehearsals/` for rehearsal evidence bundles and summarizes them for dashboard use.

## Evidence Exposed
The rehearsal evidence surface now includes:
- rehearsal history
- PASS/WARN/FAIL summaries
- retry drill outcomes
- rollback drill outcomes
- queue drill outcomes
- dead-letter drill outcomes
- telemetry validation summaries
- operator intervention summaries
- rehearsal timeline view
- artifact summaries
- operational health indicators
- staging-only warning banners

## Frontend Surfaces Added
The Command Centre dashboard now renders a new read-only section for operational rehearsal evidence:
- latest rehearsal summary
- drill outcome cards
- rehearsal timeline
- rehearsal history table
- warning banners for staging-only operator intervention

The dashboard remains read-only and does not expose any live submission controls or credentials.

## Safety Boundaries
The evidence surfaces are constrained to:
- staging-only rehearsal runtime evidence
- sandbox-generated JSON artifacts
- read-only GET endpoints
- no production database access
- no production queue access
- no production credential display
- no submission or orchestration controls

## Validation
Verified by:
- `python3 -m py_compile app/services/operational_rehearsal_service.py app/api/rfq_lifecycle_api.py tests/test_operational_rehearsal_service.py tests/test_operational_rehearsal_evidence_api.py tests/test_main_runtime_surface.py`
- `/Users/cash/Documents/.venv/bin/python -m pytest tests/test_operational_rehearsal_service.py tests/test_operational_rehearsal_evidence_api.py tests/test_main_health_status_routes.py tests/test_main_runtime_surface.py`
- `npm run build` in `etenders_acquisition/lmcp-dashboard`

## Notes
- The new evidence service reads the latest rehearsal run and history from `runtime/staging/rehearsals/`.
- The dashboard uses the evidence service only for display and does not mutate any rehearsal state.
