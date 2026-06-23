# Operational Rehearsal Execution Report

## Scope
This report records the first executable controlled operational rehearsal runner for LMCP staging validation.

The runner is implemented in [`scripts/run_operational_rehearsal.py`](/Users/cash/Documents/scripts/run_operational_rehearsal.py) and is intentionally constrained to:
- staging-only execution
- dry-run protections
- submission-lock verification
- structured telemetry emission
- evidence artifact capture under `runtime/staging/rehearsals/`

It does not enable live submissions, use production credentials, access production queues, or touch production databases.

## Supported Rehearsal Scenarios
The runner supports these rehearsal modes:
- normal RFQ rehearsal
- retry rehearsal
- queue congestion rehearsal
- worker recovery rehearsal
- dead-letter rehearsal
- rollback rehearsal
- telemetry validation rehearsal

Each scenario executes in its own isolated sandbox and writes a per-scenario evidence bundle.

## Execution Sequence
The runner follows this sequence:
1. Load the staging environment contract from `scripts/validate_staging_environment.py`.
2. Verify required staging variables, service declarations, isolation rules, telemetry configuration, and dry-run protections.
3. Abort immediately if any critical staging contract check fails.
4. Create a rehearsal run directory under `runtime/staging/rehearsals/<run_id>/`.
5. Execute each rehearsal scenario in a temporary sandbox with isolated runtime paths.
6. Create and verify a staging-only submission lock before each rehearsal stage.
7. Emit structured telemetry for request, worker, RFQ lifecycle, and operational events.
8. Capture scenario evidence artifacts and an overall summary.
9. Write `latest_operational_rehearsal.json` and `latest_operational_rehearsal.txt` for quick operator review.

## Evidence Artifacts
The latest successful rehearsal run produced:
- Run ID: `20260623T093020Z-operational-8fbad692`
- Evidence root: `runtime/staging/rehearsals/20260623T093020Z-operational-8fbad692/`

The bundle includes:
- `environment_contract.json`
- `operational_rehearsal_summary.json`
- `operational_rehearsal_summary.txt`
- per-scenario JSON summaries
- latest pointer files:
  - `runtime/staging/rehearsals/latest_operational_rehearsal.json`
  - `runtime/staging/rehearsals/latest_operational_rehearsal.txt`

## Summary
Latest execution result:
- `PASS: 54 WARN: 0 FAIL: 0`
- Scenario status: all scenarios passed

Per-scenario status:
- `normal_rfq`: PASS
- `retry_rehearsal`: PASS
- `queue_congestion_rehearsal`: PASS
- `worker_recovery_rehearsal`: PASS
- `dead_letter_rehearsal`: PASS
- `rollback_rehearsal`: PASS
- `telemetry_validation_rehearsal`: PASS

## Safety Guarantees
The runner explicitly verifies and enforces:
- staging-only execution
- dry-run protections
- final automation disabled
- no production DB URLs
- no production queue hosts
- no production credential paths
- submission lock presence before rehearsal execution
- hard blocking of `SUBMITTED` transitions
- rollback by sandbox state restoration only

## Telemetry Surfaces Emitted
The runner emits structured telemetry for:
- operational rehearsal lifecycle events
- worker heartbeat events
- request tracing events
- RFQ lifecycle transitions
- queue pressure and recovery observations

## Operational Notes
- Queue and worker telemetry is treated as observational for the rehearsal runner.
- The runner is dependency-light and uses a local guard-lock shim so it does not depend on live guard imports or external credentials.
- The sandboxed lifecycle telemetry may report degraded worker/broker observations in offline environments; this does not fail the rehearsal unless it violates a safety gate.

## Verification
Validated by:
- `python3 scripts/run_operational_rehearsal.py`

The command exited cleanly and produced the evidence bundle above.
