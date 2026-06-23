# Operational Remediation Governance Report

This report documents the read-only remediation governance layer for recurring pilot-cycle exceptions.

## What was added

- A staging-only remediation governance service derived from:
  - `runtime/staging/pilot-cycles/`
  - `runtime/staging/governance-exports/`
  - the operational exception classification surface
- Read-only API endpoints:
  - `GET /rfq-lifecycle/remediation`
  - `GET /rfq-lifecycle/remediation/latest`
  - `GET /rfq-lifecycle/remediation/history`
- A Command Centre remediation panel covering:
  - remediation actions
  - remediation ownership
  - remediation deadlines
  - accepted operational risk classification
  - unresolved blocker escalation
  - remediation completion tracking
  - operational risk closure summaries
  - unresolved remediation indicators
  - overdue remediation warnings
  - recurring unresolved anomaly tracking
  - remediation governance history

## What the remediation layer surfaces

- Read-only remediation ownership by exception category
- Deadline tracking derived from staging evidence timestamps and severity
- Accepted-risk classification for low-risk open items
- Blocker identification for governance and platform-impacting anomalies
- Closure summaries for resolved and unresolved issues

## Safety properties

- Read-only
- Staging-only
- No live submission controls
- No production connectivity
- No irreversible actions
- No scheduler or orchestration changes

## Governance intent

The remediation layer is advisory and visibility-only. It does not change runtime workflow behavior, submission authority, or pilot authorization. It exists to explain who owns a recurring exception, when it is due, whether the risk is accepted, and whether it is overdue or blocking staging progress.

## Verification

The remediation surfaces are covered by backend service tests, API tests, runtime surface tests, and the Command Centre build.
