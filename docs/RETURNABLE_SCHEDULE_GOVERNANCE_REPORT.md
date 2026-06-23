# Returnable Schedule Governance Report

## Scope
This surface provides read-only staging governance for mandatory returnables, annexures, schedules, declarations, and bid-response completeness.

## Runtime Surface
- Backend service: `app.services.returnable_governance_service.ReturnableGovernanceService`
- Read-only routes:
  - `GET /rfq-lifecycle/returnable-governance`
  - `GET /rfq-lifecycle/returnable-governance/latest`
  - `GET /rfq-lifecycle/returnable-governance/history`
- Command Centre panel: `Returnable Schedule Governance`

## Governance Coverage
The surface classifies and scores:
- annexures
- mandatory returnables
- pricing schedules
- declarations
- technical schedules
- compulsory forms
- mandatory attachments

It also reports:
- incomplete-returnable warnings
- missing-annexure indicators
- unsigned-returnable warnings
- bid-response completeness scoring
- returnable governance history

## Safety Constraints
- Staging-only, read-only visibility
- No autonomous document fabrication
- No irreversible actions
- No production connectivity required
- Dry-run protections remain authoritative

## Verification Expectations
- `py_compile` must succeed for the service, API, and runtime surface tests
- `pytest` must pass for the returnable governance service and API tests
- The frontend build must continue to pass
- The readiness declaration surface must continue to load
