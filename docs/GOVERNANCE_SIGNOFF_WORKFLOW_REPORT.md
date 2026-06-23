# Governance Sign-Off Workflow Report

This workflow exposes read-only governance review surfaces for staged pilot authorization. It is derived entirely from the latest evidence pack under `runtime/staging/evidence-packs/` and does not modify runtime state.

## Review surfaces

- Latest evidence pack
- Evidence pack history
- Readiness score
- PASS/WARN/FAIL history
- Rehearsal cadence
- Rollback evidence
- Queue stability evidence
- Telemetry health evidence
- Submission lock verification

## Review panels

- Operator sign-off checklist
- Governance review checklist
- Pilot authorization status
- NO-GO indicators
- Staging-only warning banners

## Authorization model

The workflow is advisory only. It does not grant live submission authority, does not expose irreversible controls, and does not surface production credentials.

The review service derives a pilot authorization status from the latest evidence pack:

- `authorized` when the evidence pack is present and the required checks pass
- `not_authorized` when any NO-GO indicator is present
- `pending_review` when no evidence pack exists yet

## NO-GO conditions

- No pilot evidence pack is available
- Readiness score is below the threshold
- Rollback evidence is missing or not PASS
- Queue stability evidence is missing or not PASS
- Telemetry health evidence is missing or not PASS
- Submission lock verification is missing or not PASS
- Dry-run enforcement verification is missing or not PASS

## Safety properties

- Read-only
- Staging-only
- No live submission controls
- No irreversible actions
- No production credentials

## Evidence source

The latest evidence pack is generated from staging rehearsal output and written to `runtime/staging/evidence-packs/` as a timestamped bundle. The Command Centre now reads this evidence to present governance review panels for human sign-off.

## Validation command

The review surface is validated through the standard backend and frontend checks used for the staging dashboard, plus the read-only evidence pack generator.
