# Handwritten & Signature Governance Report

## Scope
This report documents the read-only, staging-only governance surface for procurement workflows that require wet signatures, handwritten declarations, witnesses, commissioner attestations, affidavits, or manual attestation.

## Runtime Surface
- Backend service: `app.services.signature_governance_service.SignatureGovernanceService`
- Read-only routes:
  - `GET /rfq-lifecycle/signature-governance`
  - `GET /rfq-lifecycle/signature-governance/latest`
  - `GET /rfq-lifecycle/signature-governance/history`
- Command Centre panel: `Handwritten & Signature Governance`

## Governance Signals
The surface classifies:
- wet-signature requirements
- handwritten-declaration requirements
- witness requirements
- commissioner requirements
- affidavit requirements
- manual-attestation routing and supervision

It also reports:
- human-completion-required warnings
- unsigned-document indicators
- affidavit-readiness indicators
- signature-governance scoring
- manual-attestation history
- operator-assignment readiness

## Safety Constraints
- Staging-only, read-only visibility
- No autonomous signature generation
- No handwriting simulation authority
- No irreversible actions
- No production connectivity required
- Dry-run protections remain authoritative

## Verification Expectations
- `py_compile` must succeed for the service, API, and runtime surface tests
- `pytest` must pass for the signature governance service and API tests
- The frontend build must continue to pass
- The readiness declaration surface must continue to load
