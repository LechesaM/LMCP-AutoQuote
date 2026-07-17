# Live RFQ Store Recovery Audit

## Purpose

`scripts/audit_live_rfq_store.py` is a read-only diagnostic for finding the break between current RFQ acquisition, the Live RFQ Store, and the frontend operational pipeline.

The audit identifies which implementation backs the relevant GET endpoints, which physical files or containers back those endpoints, whether `app/services/live_rfq_store.p` is active, which source files can write to the Live RFQ Store, which harvesters write RFQ-like data elsewhere, Docker mount alignment, runtime file freshness, and a final recovery classification.

## Safety Constraints

The audit must not mutate operational state. It only uses Python source inspection, runtime file metadata and JSON reads, Docker inspection/log commands, environment/compose inspection, and GET requests.

The script does not send POST, PUT, PATCH, or DELETE requests. It does not clear, migrate, overwrite, repopulate, truncate, or delete any store.

## How To Run

From the repository root:

```bash
.venv/bin/python scripts/audit_live_rfq_store.py
```

With the recovery output path:

```bash
mkdir -p /Users/Shared/LMCP-Recovery-2026-07-15/live-rfq-store-audit

.venv/bin/python scripts/audit_live_rfq_store.py \
  --base-url http://localhost:8000 \
  --container lmcp-api \
  --log-hours 168 \
  --output /Users/Shared/LMCP-Recovery-2026-07-15/live-rfq-store-audit/live-rfq-store-report.json \
  --verbose
```

Validate syntax without running the audit:

```bash
.venv/bin/python -m py_compile scripts/audit_live_rfq_store.py
```

## Classification Meanings

`STORE_STALE`: the active Live RFQ Store exists but has not been refreshed recently. Repair should focus on the producer path that should promote current RFQs into `runtime/live_rfqs.json`.

`PRODUCER_PATH_MISMATCH`: code intended to write the Live RFQ Store is wired to the wrong object, wrong branch, wrong endpoint, or broken call site. Repair should be limited to the producer bridge.

`ACQUISITION_NOT_RUNNING`: the acquisition worker or scheduler has no evidence of recent RFQ writes. Repair should focus on worker scheduling or queue health.

`ACQUISITION_WRITES_ELSEWHERE`: current RFQ-like records are being produced, but the active Live RFQ Store is not receiving them. Repair should bridge the active acquisition output into the store without repopulating historical data.

`CONTAINER_VOLUME_MISMATCH`: API and worker containers do not appear to share the same runtime mount, or the API uses container-local storage. Repair should align mounts before any store-level change.

`CURRENT_DATA_NOT_AVAILABLE`: no current RFQ-like data was found in the inspected sources. Repair should start with acquisition source health, not store rebuilding.

`INCONCLUSIVE`: evidence is insufficient or conflicting. Review `errors`, `route_implementations`, `store_candidates`, `producer_candidates`, `docker_mounts`, and `mismatches` in the JSON report.

## Prohibited During Recovery

Do not run these commands or endpoints during this recovery phase:

```text
POST /supply-command/live-rfqs/clear
POST /supply-command/live-rfqs/upsert
POST /supply-command/live-rfqs/bulk-upsert
POST /supply-command/run
POST /rfq-lifecycle/cleanup-runtime
```

Do not clear, delete, truncate, migrate, overwrite, or repopulate Docker volumes, PostgreSQL data, Redis data, runtime JSON files, or harvested documents.

Do not merge branches, commit, push, or modify frontend source as part of the audit.
