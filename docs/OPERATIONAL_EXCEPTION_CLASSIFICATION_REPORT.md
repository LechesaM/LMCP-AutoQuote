# Operational Exception Classification Report

This report documents the read-only institutional anomaly classification and remediation tracking layer for recurring pilot cycles.

## What was added

- A staging-only exception classification service derived from `runtime/staging/pilot-cycles/` and `runtime/staging/governance-exports/`.
- Read-only API endpoints:
  - `GET /rfq-lifecycle/exceptions`
  - `GET /rfq-lifecycle/exceptions/latest`
  - `GET /rfq-lifecycle/exceptions/history`
- A Command Centre exception panel covering:
  - transient failures
  - systemic failures
  - retry exhaustion
  - telemetry degradation
  - queue instability
  - operator intervention anomalies
  - governance compliance failures
  - remediation status tracking
  - unresolved exception tracking
  - resolved exception history
  - operational risk indicators
  - recurring anomaly summaries

## What the exception layer surfaces

- Read-only classification of recurring pilot-cycle anomalies
- Remediation state for open and resolved issues
- Operational risk indicators for governance, queue, worker, telemetry, retry, and operator signals
- Historical anomaly tracking across staging pilot cycles

## Safety properties

- Read-only
- Staging-only
- No live submission controls
- No production connectivity
- No irreversible actions
- No scheduler or orchestration changes

## Governance intent

The exception layer is advisory and visibility-only. It does not alter pilot authorization, runtime workflow behavior, or submission authority. It exists to explain why recurring pilot cycles are clean, warning, or blocked from a governance perspective.

## Verification

The exception surfaces are covered by backend service tests, API tests, runtime surface tests, and the Command Centre build.
