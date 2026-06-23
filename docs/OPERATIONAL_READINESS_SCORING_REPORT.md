# Operational Readiness Scoring Report

## Scope
This change adds read-only operational readiness scoring and trend visibility on top of the existing staging rehearsal evidence.

It does not enable live submissions, remove dry-run protections, require production connectivity, or expose any irreversible action.

## Backend Surfaces Added
The RFQ lifecycle router now exposes these read-only readiness endpoints:
- `GET /rfq-lifecycle/rehearsals/readiness`
- `GET /rfq-lifecycle/rehearsals/readiness/history`

These endpoints are backed by [`app/services/operational_rehearsal_service.py`](/Users/cash/Documents/app/services/operational_rehearsal_service.py), which derives readiness metrics from `runtime/staging/rehearsals/`.

## Readiness Model
The readiness score is derived from the latest rehearsal history and includes:
- rehearsal success rate
- retry recovery success
- rollback success
- queue stability
- worker stability
- telemetry health
- DLQ escalation frequency
- operator intervention frequency

The service also exposes:
- operational trend summaries
- readiness score history
- rehearsal cadence visibility
- warning threshold indicators

## Current Snapshot
Latest readiness snapshot from the existing staging rehearsal evidence:
- readiness score: `100.00`
- readiness grade: `ready`
- trend: `stable`
- cadence: `1` run in the last 7 days

## Frontend Surfaces Added
The Command Centre now renders a read-only readiness area with:
- readiness score card
- readiness trend card
- stability indicators card
- readiness score history table

The dashboard is display-only. No controls or submission actions were added.

## Safety Boundaries
The readiness surfaces are constrained to:
- staging rehearsal artifacts only
- read-only GET endpoints
- no production database access
- no production queue access
- no production credential display
- no operational controls or irreversible actions

## Validation
Verified by:
- `python3 -m py_compile app/services/operational_rehearsal_service.py app/api/rfq_lifecycle_api.py tests/test_operational_rehearsal_service.py tests/test_operational_rehearsal_readiness_service.py tests/test_operational_rehearsal_evidence_api.py tests/test_operational_rehearsal_readiness_api.py tests/test_main_runtime_surface.py`
- `/Users/cash/Documents/.venv/bin/python -m pytest tests/test_operational_rehearsal_service.py tests/test_operational_rehearsal_readiness_service.py tests/test_operational_rehearsal_evidence_api.py tests/test_operational_rehearsal_readiness_api.py tests/test_main_health_status_routes.py tests/test_main_runtime_surface.py`
- `npm run build` in `etenders_acquisition/lmcp-dashboard`

## Notes
- The readiness history and trend are derived from the rehearsal run summaries in `runtime/staging/rehearsals/`.
- The score is intentionally read-only and is used only for staging readiness visibility in the Command Centre.
