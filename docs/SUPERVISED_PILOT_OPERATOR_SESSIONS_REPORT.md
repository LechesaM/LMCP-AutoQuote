# Supervised Pilot Operator Sessions Report

This change introduces the read-only supervised operator session layer for LMCP staging pilot operations.

## Scope

- New backend service: `app.services.pilot_operator_session_service.PilotOperatorSessionService`
- New read-only API routes:
  - `GET /rfq-lifecycle/operator-sessions`
  - `GET /rfq-lifecycle/operator-sessions/latest`
  - `GET /rfq-lifecycle/operator-sessions/history`
- New Command Centre panel:
  - `Supervised Pilot Operator Sessions`

## Tracked Session Data

The operator-session layer derives its view from existing staging artifacts:

- active operator sessions
- supervised RFQ assignments
- operator acknowledgements
- approval checkpoints
- escalation acknowledgements
- pilot supervision windows

## Governance Outputs

The surface exposes:

- operator supervision scoring
- unattended RFQ warnings
- supervision lapse indicators
- escalation SLA tracking

## Operational Guardrails

The operator-session surface is read-only and staging-only.

- No autonomous submission authority is exposed.
- No irreversible actions are enabled.
- Dry-run protections remain active.
- Governance layers remain authoritative.

## Verification

The contract is covered by:

- service tests for active and blocked supervision paths
- API tests for the operator-session routes
- runtime surface coverage for the new routes

