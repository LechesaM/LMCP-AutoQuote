# API Restart Readiness

Audit date: 2026-07-16
Final state: SAFE_TO_RESTART_WITH_KNOWN_ROUTE_CHANGES

## Decision

Do not restart `lmcp-api` without operator approval and pre-restart evidence capture.

The duplicate SBD routes are resolved, RFQ lifecycle/manual-pricing compatibility routes are restored, source router import is clean, and high-risk source-only route families are disabled by default through the operational route baseline.

Import/OpenAPI generation now has no persistent write calls in focused tests. During validation, secondary runtime reporting files (`analytics.json`, `telemetry.json`, `mission_control_snapshot.json`, `submission_history.json`) continued to change between repeated hash checks without import/OpenAPI activity, indicating an external/background runtime writer. The protected Live RFQ Store and lifecycle item store remained unchanged.

## Current Evidence

| Metric | Value |
| --- | ---: |
| Running paths | 351 |
| Running method/path pairs | 359 |
| Source paths | 295 |
| Source method/path pairs | 303 |
| Source loaded routers | 54 |
| Source failed routers | 0 |
| Source duplicate route pairs | 0 |
| Source disabled routers | 56 |
| Running-only method/path pairs | 56 |
| Source-only method/path pairs | 0 |
| Shared routes with operation-ID drift | 3 |

## Improvements Completed

- `GET /sbd-intelligence/status` has one canonical source owner.
- `POST /sbd-intelligence/complete` has one canonical source owner.
- `app.api.tender_form_intelligence_api` now owns `/tender-form-intelligence/*`.
- Six tender-form running-only routes are now source-present.
- Source duplicate route count is zero.
- Autonomous defaults are disabled in `app.autonomous_api` and `app.api.autonomous_api`.
- Four RFQ lifecycle/manual-pricing running-only routes are restored with matching historical operation IDs.
- `validate-visible-opportunities` compatibility defaults are dry-run/read-only and do not mutate Live RFQ Store or lifecycle state.
- Manual-pricing compatibility avoids Live RFQ Store upserts.
- `GET /health/workflows` is restored as read-only workflow/router health compatibility.
- `GET /system/control/effective-status` is restored as read-only control compatibility.
- Importing `app.main` and generating OpenAPI no longer performs persistent directory or file writes.
- High-risk source-only route families are default-denied before import through `app/core/router_activation.py`.
- Operational route baseline verification passes.
- Focused SBD and autonomous safety tests pass.

## Remaining Blockers

There are no remaining technical blockers to a controlled restart under the documented baseline. Known route changes must be accepted by the operator:

1. Dashboard manual-review and go-live pilot routes remain waived/pending operator decision:
   - `/dashboard/manual-review/*`
   - `/go-live/pilot-runs`
   - `/go-live/pilot-runs/report`
   - `/go-live/readiness`
2. Autonomous legacy compatibility routes are formally waived as superseded:
   - `GET /autonomous/health`
   - `POST /autonomous/run-sync`
3. 56 method/path pairs from the stale running process will not be present under the controlled source baseline.
4. Source-only method/path pairs are reduced to 0 by default-denying high-risk families.
5. Submission/upload/autonomous source-only families are disabled by default:
   - `/v46-auto-submission/*`
   - `/v47-final-submit/*`
   - `/v47-portal-submission/*`
   - `/v47-smart-upload/*`
   - `/v48-autonomous/*`
6. Three shared `/autonomous` operation IDs differ from the running process.
7. Live GET probes to `localhost:8000` previously failed from this environment, so pre-restart capture should retry them immediately before restart.

## Route Activation Manifest

Created `config/lmcp_v2_operational_route_baseline.json` and updated `config/recovery_route_activation_manifest.json`.

The operational baseline is wired into startup through `app/core/router_activation.py`. It marks:

- Required health, system control, RFQ lifecycle, quote compilation, SBD, audit, proof, dashboard, and go-live guard routes as enabled.
- High-risk acquisition, browser automation, upload, final submission, autonomous, and eTenders acquisition/download families as disabled by default.
- Explicit opt-in via `LMCP_ENABLE_HIGH_RISK_ROUTERS=true` or `LMCP_ENABLE_ROUTER_FAMILIES=<router_name>`.

## Safe Restart Plan

Do not execute during this audit.

```bash
mkdir -p /Users/Shared/LMCP-Recovery-2026-07-15/pre-restart
curl -sS http://localhost:8000/health \
  -o /Users/Shared/LMCP-Recovery-2026-07-15/pre-restart/health-before.json
curl -sS http://localhost:8000/openapi.json \
  -o /Users/Shared/LMCP-Recovery-2026-07-15/pre-restart/openapi-before.json
docker inspect lmcp-api \
  > /Users/Shared/LMCP-Recovery-2026-07-15/pre-restart/docker-inspect-before.json
shasum -a 256 runtime/live_rfqs.json runtime/rfq_lifecycle/rfqs.json \
  > /Users/Shared/LMCP-Recovery-2026-07-15/pre-restart/runtime-store-shas-before.txt
stat -f '%z %m %N' runtime/live_rfqs.json runtime/rfq_lifecycle/rfqs.json \
  > /Users/Shared/LMCP-Recovery-2026-07-15/pre-restart/runtime-store-stat-before.txt
git status --short > /Users/Shared/LMCP-Recovery-2026-07-15/pre-restart/git-status-before.txt
git diff > /Users/Shared/LMCP-Recovery-2026-07-15/pre-restart/source-diff-before.patch
```

Restart command, only after operator approval:

```bash
docker compose restart api
```

Immediate GET-only checks:

```bash
curl -sS http://localhost:8000/health
curl -sS http://localhost:8000/openapi.json
curl -sS http://localhost:8000/sbd-intelligence/status
curl -sS http://localhost:8000/tender-form-intelligence/status
curl -sS http://localhost:8000/rfq-lifecycle/status
curl -sS http://localhost:8000/rfq-lifecycle/items
curl -sS http://localhost:8000/supply-command/live-rfqs
curl -sS http://localhost:8000/health/workflows
curl -sS http://localhost:8000/system/control/effective-status
```

Rollback criteria:

- `/health` is unhealthy.
- Router failures reappear.
- Duplicate routes reappear.
- Autonomous default state is enabled.
- Manual submission safeguards disappear.
- Critical GET endpoints return 5xx.
- High-risk default-denied routes are unexpectedly exposed.

Rollback command, only with operator approval:

```bash
git checkout -- app/api/tender_form_intelligence_api.py app/autonomous_api.py app/api/autonomous_api.py
docker compose restart api
```

Do not use broad cleanup commands.
