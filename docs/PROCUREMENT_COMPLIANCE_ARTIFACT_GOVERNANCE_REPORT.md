# Procurement Compliance Artifact Governance Report

## Scope
This surface provides read-only staging governance for procurement compliance artifacts and certificate validity checks.

## Runtime Surface
- Backend service: `app.services.compliance_governance_service.ComplianceGovernanceService`
- Read-only routes:
  - `GET /rfq-lifecycle/compliance-governance`
  - `GET /rfq-lifecycle/compliance-governance/latest`
  - `GET /rfq-lifecycle/compliance-governance/history`
- Command Centre panel: `Procurement Compliance Artifacts`

## Governance Coverage
The surface classifies and scores:
- tax-clearance artifacts
- BBBEE artifacts
- CIDB artifacts
- COIDA artifacts
- NHBRC artifacts
- company-registration artifacts
- bank-letter artifacts
- certificate expiry validity

It also reports:
- missing-artifact warnings
- invalid-artifact indicators
- expiry warnings
- compliance-readiness scoring
- artifact governance history

## Safety Constraints
- Staging-only, read-only visibility
- No autonomous document forgery
- No production credential usage
- No irreversible actions
- No production connectivity required
- Dry-run protections remain authoritative

## Verification Expectations
- `py_compile` must succeed for the service, API, and runtime surface tests
- `pytest` must pass for the compliance governance service and API tests
- The frontend build must continue to pass
- The readiness declaration surface must continue to load
