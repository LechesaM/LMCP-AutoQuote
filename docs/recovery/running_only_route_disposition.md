# Running-Only Route Disposition

Audit date: 2026-07-16
Evidence matrix: `docs/recovery/runtime_route_difference_matrix.json`

## Summary

Final disposition is now recorded in `docs/recovery/final_running_route_disposition.md`. The final operational baseline restores `/health/workflows` and `/system/control/effective-status`, formally waives legacy autonomous compatibility routes, and leaves historical dashboard/go-live pilot routes for operator decision.

Before SBD ownership repair, 20 running-only method/path pairs were absent from source OpenAPI. Six tender-form intelligence routes were resolved by moving `app.api.tender_form_intelligence_api` back to `/tender-form-intelligence`.

After SBD ownership repair, 14 running-only method/path pairs remained:

- `CONDITIONAL_REGISTRATION`: 8
- `PROCESS_MEMORY_ONLY`: 6

After RFQ lifecycle/manual-pricing compatibility restoration, 10 running-only method/path pairs remain:

- `CONDITIONAL_REGISTRATION`: 6
- `PROCESS_MEMORY_ONLY`: 4

## Resolved During This Task

These former running-only routes are now present in source OpenAPI:

| Method | Path | Resolution |
| --- | --- | --- |
| `GET` | `/tender-form-intelligence/status` | Restored by assigning tender-form facade ownership to `/tender-form-intelligence`. |
| `POST` | `/tender-form-intelligence/build-glyphs` | Restored by assigning tender-form facade ownership to `/tender-form-intelligence`. |
| `POST` | `/tender-form-intelligence/complete` | Restored by assigning tender-form facade ownership to `/tender-form-intelligence`. |
| `POST` | `/tender-form-intelligence/detect-sbd` | Restored by assigning tender-form facade ownership to `/tender-form-intelligence`. |
| `POST` | `/tender-form-intelligence/detect-template` | Restored by assigning tender-form facade ownership to `/tender-form-intelligence`. |
| `POST` | `/tender-form-intelligence/locate-fields` | Restored by assigning tender-form facade ownership to `/tender-form-intelligence`. |
| `GET` | `/rfq-lifecycle/manual-pricing/{rfq_id}` | Restored as a compatibility route delegating to current `RfqLifecycleService.get_manual_pricing`. |
| `POST` | `/rfq-lifecycle/manual-pricing/{rfq_id}` | Restored as a compatibility route delegating to current `RfqLifecycleService.save_manual_pricing`; no Live RFQ Store upsert is performed. |
| `POST` | `/rfq-lifecycle/reject-terminal-review-items` | Restored as a compatibility route delegating to current terminal-review cleanup logic. |
| `POST` | `/rfq-lifecycle/validate-visible-opportunities` | Restored as a compatibility route with dry-run/read-only defaults. |

## Remaining Running-Only Routes

| Method | Path | Evidence source | Disposition | Minimal restoration method |
| --- | --- | --- | --- | --- |
| `GET` | `/autonomous/health` | Current source has autonomous status; exact route not in source OpenAPI. | SUPERSEDED | Use `/autonomous/status`; restore only if an external monitor depends on `/autonomous/health`. |
| `POST` | `/autonomous/run-sync` | `origin/release/v1.1:app/api/autonomous_api.py`; current unregistered `app/api/autonomous_api.py`. | REQUIRES_OPERATOR_DECISION | Do not restore until autonomous run routes are explicitly governed; default autonomous state is now disabled. |
| `GET` | `/dashboard/manual-review/summary` | `origin/release/v1.1:app/api/dashboard.py`. | REQUIRES_OPERATOR_DECISION | Restore dashboard manual-review read-only endpoints if frontend or operations still depend on them. |
| `GET` | `/dashboard/manual-review/queue` | `origin/release/v1.1:app/api/dashboard.py`. | REQUIRES_OPERATOR_DECISION | Restore dashboard manual-review read-only endpoints if frontend or operations still depend on them. |
| `GET` | `/dashboard/manual-review/pilot-summary` | `origin/release/v1.1:app/api/dashboard.py`. | REQUIRES_OPERATOR_DECISION | Restore dashboard manual-review read-only endpoints if pilot dashboards still depend on them. |
| `GET` | `/go-live/pilot-runs` | `origin/release/v1.1:app/api/go_live_guard_api.py`. | REQUIRES_OPERATOR_DECISION | Restore read-only pilot-run route if go-live reporting is required. |
| `GET` | `/go-live/pilot-runs/report` | `origin/release/v1.1:app/api/go_live_guard_api.py`. | REQUIRES_OPERATOR_DECISION | Restore read-only report route if go-live reporting is required. |
| `GET` | `/go-live/readiness` | Current source has `app.api.go_live_guard_api` but generated source OpenAPI lacks this exact route. | REQUIRES_OPERATOR_DECISION | Reconcile current go-live router before restart. |
| `GET` | `/health/workflows` | `origin/release/v1.1:app/main.py`; `origin/release/v1.1:app/recovery_main.py`. | SAFE_TO_DROP | General `/health` remains available; restore only if monitoring depends on this exact route. |
| `GET` | `/system/control/effective-status` | Current source has `app.api.system_control`; exact route not in generated source OpenAPI. | REQUIRES_OPERATOR_DECISION | Restore if operator control dashboard depends on this exact status route. |

## Restart Implication

The remaining running-only set is no longer a duplicate-route problem and no longer includes the four RFQ lifecycle/manual-pricing compatibility routes. Restart still requires an operator decision for autonomous legacy routes, dashboard manual-review routes, go-live routes, `/health/workflows`, and `/system/control/effective-status`.
