# Pilot Rehearsal Summary Export Report

The pilot rehearsal summary exporter is a read-only staging utility that packages governance approval material from the latest pilot evidence pack into an operator-ready export bundle.

## Generated outputs

Each run creates a timestamped export bundle under `runtime/staging/governance-exports/` containing:

- `pilot_rehearsal_summary.json`
- `pilot_rehearsal_summary.md`

A read-only `latest_pilot_rehearsal_summary.json` snapshot is also written at the root of `runtime/staging/governance-exports/`.

## Included content

- Readiness score summary
- PASS/WARN/FAIL trends
- Rehearsal cadence summary
- Rollback evidence summary
- Queue stability summary
- Telemetry health summary
- Submission lock verification
- Dry-run enforcement verification
- NO-GO condition summary
- Operator sign-off section
- Governance review section
- Pilot authorization recommendation

## Safety properties

- Staging-only
- Read-only
- No live submission controls
- No production credentials
- No irreversible actions

## Evidence source

The exporter reads the latest evidence pack from `runtime/staging/evidence-packs/` via the read-only governance review service and translates it into a governance approval summary for operators.

## Validation command

```bash
python3 scripts/export_pilot_rehearsal_summary.py
```

The exporter exits cleanly after writing the JSON and markdown summaries and reporting the readiness score and NO-GO status to stdout.
