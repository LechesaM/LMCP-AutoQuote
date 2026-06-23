# Pilot Evidence Pack Report

The pilot evidence pack generator is a read-only staging utility that compiles formal operational evidence from `runtime/staging/rehearsals/` into a timestamped bundle under `runtime/staging/evidence-packs/`.

## What the generator includes

- Readiness summary
- Rehearsal history summary
- PASS/WARN/FAIL trend summary
- Retry recovery evidence
- Rollback evidence
- Queue stability evidence
- Worker stability evidence
- Telemetry health evidence
- Submission-lock verification
- Dry-run enforcement verification
- Operator intervention summary

## Output format

Each run creates a timestamped evidence pack directory containing:

- `pilot_evidence_pack.json`
- `pilot_evidence_pack.md`

A read-only `latest_pilot_evidence_pack.json` snapshot is also written at the root of `runtime/staging/evidence-packs/` for convenience.

## Safety and scope

- Staging-only
- Read-only
- No live submissions
- No production credentials
- No production queues or databases
- No irreversible operations

## Submission-lock handling

The generator checks the staging submission-lock file from `LMCP_SUBMISSION_LOCK_FILE` when configured, or falls back to `runtime/staging/go_live_guards/submission_locks.json`.

The staging lock file is explicit and must show:

- `final_automation_disabled = true`
- `live_portal_submission_disabled = true`
- `production_credentials_disabled = true`
- `dry_run_mode_required = true`
- `submission_execution_allowed = false`

The evidence pack records the configured lock source and verifies the file contents in read-only mode.

## Dry-run enforcement

Dry-run enforcement is verified from the latest rehearsal summary in `runtime/staging/rehearsals/latest_operational_rehearsal.json`, which records:

- `live_submissions = false`
- `production_queues = false`
- `production_databases = false`
- `irreversible_operations = false`

## Validation command

```bash
python3 scripts/generate_pilot_evidence_pack.py
```

The script exits cleanly when the pack is generated successfully and reports the PASS/WARN/FAIL breakdown in stdout.
