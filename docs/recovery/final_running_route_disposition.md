# Final Running-Only Route Disposition

Audit date: 2026-07-16
Baseline: `config/lmcp_v2_operational_route_baseline.json`

## Summary

The 10 remaining running-only method/path pairs from the pre-recovery process were reviewed against current source, historical source evidence, current equivalents, and restart safety. Two read-only compatibility routes were retained. Eight routes were formally waived as superseded or requiring future operator decision; none were restored wholesale from historical router stacks.

## Disposition Matrix

| Method | Path | Running operation ID | Historical source | Current equivalent | Side effects | Active frontend / monitoring role | Disposition | Confidence | Restart impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/health/workflows` | `workflow_health_health_workflows_get` | `origin/release/v1.1:app/main.py` | New read-only `app.main.workflow_health` | None | Health/workflow monitoring compatibility | `RETAIN_AS_HEALTH_COMPATIBILITY` | HIGH | Required compatibility retained. |
| `GET` | `/system/control/effective-status` | `system_control_effective_status_system_control_effective_status_get` | Current source text and historical route evidence | New read-only `app.api.system_control.system_control_effective_status` | None; reads existing state if present and does not initialize it | Operator-control dashboard compatibility | `RETAIN_AS_CONTROL_COMPATIBILITY` | HIGH | Required compatibility retained. |
| `GET` | `/autonomous/health` | `autonomous_health_autonomous_health_get` | `origin/release/v1.1:app/api/autonomous_api.py` | `/autonomous/status` | Historical read-only status | Not required when `/autonomous/status` is present | `FORMALLY_WAIVE_AS_SUPERSEDED` | HIGH | Route may disappear after restart; current safer status route remains. |
| `POST` | `/autonomous/run-sync` | `run_sync_autonomous_run_sync_post` | `origin/release/v1.1:app/api/autonomous_api.py` | `/autonomous/run-once`, with autonomous default disabled | Would execute autonomous workflow if enabled | Not restored for recovery safety | `FORMALLY_WAIVE_AS_SUPERSEDED` | HIGH | Legacy sync trigger intentionally absent; autonomous remains disabled by default. |
| `GET` | `/dashboard/manual-review/summary` | `dashboard_manual_review_summary_dashboard_manual_review_summary_get` | `origin/release/v1.1:app/api/dashboard.py` | `/dashboard/summary`, `/quote-compilation/candidates`, RFQ lifecycle queues | Historical DB-backed quote-review read | No current active frontend dependency proven | `REQUIRES_OPERATOR_DECISION` | MEDIUM | Restart may drop historical dashboard manual-review summary. |
| `GET` | `/dashboard/manual-review/queue` | `dashboard_manual_review_queue_dashboard_manual_review_queue_get` | `origin/release/v1.1:app/api/dashboard.py` | `/quote-compilation/candidates`, `/rfq-lifecycle/items` | Historical DB-backed quote-review read | No current active frontend dependency proven | `REQUIRES_OPERATOR_DECISION` | MEDIUM | Restart may drop historical manual-review queue. |
| `GET` | `/dashboard/manual-review/pilot-summary` | `dashboard_manual_review_pilot_summary_dashboard_manual_review_pilot_summary_get` | `origin/release/v1.1:app/api/dashboard.py` | `/dashboard/summary`, go-live guard summary | Historical pilot-report read | No current active frontend dependency proven | `REQUIRES_OPERATOR_DECISION` | MEDIUM | Restart may drop historical pilot summary. |
| `GET` | `/go-live/pilot-runs` | `go_live_pilot_runs_go_live_pilot_runs_get` | `origin/release/v1.1:app/api/go_live_guard_api.py` | `/go-live-guards/summary` | Historical pilot-run read | No current active dependency proven | `REQUIRES_OPERATOR_DECISION` | MEDIUM | Restart may drop historical pilot-run listing. |
| `GET` | `/go-live/pilot-runs/report` | `go_live_pilot_runs_report_go_live_pilot_runs_report_get` | `origin/release/v1.1:app/api/go_live_guard_api.py` | `/go-live-guards/summary` | Historical pilot-report read | No current active dependency proven | `REQUIRES_OPERATOR_DECISION` | MEDIUM | Restart may drop historical pilot-run report. |
| `GET` | `/go-live/readiness` | `go_live_readiness_go_live_readiness_get` | `origin/release/v1.1:app/api/go_live_guard_api.py` | `/go-live-guards/summary` | Historical readiness read | No current active dependency proven | `REQUIRES_OPERATOR_DECISION` | MEDIUM | Restart may drop historical readiness endpoint. |

## Compatibility Routes Restored

- `GET /health/workflows`
- `GET /system/control/effective-status`

Both routes are read-only and do not create or modify runtime files during import, OpenAPI generation, or request handling.

## Formal Waivers

- `GET /autonomous/health` is superseded by `/autonomous/status`.
- `POST /autonomous/run-sync` is superseded by current controlled autonomous routes and is intentionally not restored because autonomous execution must remain disabled by default.

## Operator Decisions Still Available

Historical dashboard manual-review and go-live pilot routes are not restored in this patch because current source lacks equivalent service contracts with clear active frontend dependence. They are documented for operator review rather than restored from older router stacks.
