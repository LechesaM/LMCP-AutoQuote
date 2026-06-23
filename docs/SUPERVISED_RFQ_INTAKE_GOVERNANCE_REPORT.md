# Supervised RFQ Intake Governance Report

This change introduces the read-only supervised RFQ intake governance layer for LMCP staging pilot operations.

## Scope

- New backend service: `app.services.supervised_rfq_intake_service.SupervisedRfqIntakeService`
- New read-only API routes:
  - `GET /rfq-lifecycle/intake`
  - `GET /rfq-lifecycle/intake/latest`
  - `GET /rfq-lifecycle/intake/history`
- New Command Centre panel:
  - `Supervised RFQ Intake Governance`

## Governance Responsibilities

The intake surface evaluates:

- RFQ eligibility classification
- pilot-scope enforcement
- restricted RFQ category validation
- supervision-capacity validation
- governance approval gating
- operator assignment readiness

## Read-Only Outputs

The surface exposes:

- intake eligibility scoring
- restricted-category warnings
- supervision-capacity indicators
- governance intake decisions
- intake decision history

## Operational Guardrails

The intake surface is read-only and staging-only.

- No live submission controls are exposed.
- No production connectivity is required.
- No irreversible actions are enabled.
- Dry-run protections remain active.
- Governance layers remain authoritative.

## Verification

The contract is covered by:

- service tests for eligible and blocked intake paths
- API tests for the intake routes
- runtime surface coverage for the new routes

