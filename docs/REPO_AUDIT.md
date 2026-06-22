# Repository Audit

Date: 2026-06-22
Repo root: `/Users/cash/Documents`
Scope: repository audit only; no code changes

## Summary

This repository has one clear active backend runtime path:

- Backend API: `app.main:app`
- Worker runtime: `app.celery_app.celery_app`
- Primary runtime orchestration: `docker-compose.production.yml`
- Current local/dev orchestration: `docker-compose.yml`

The main stabilization risk is duplicate tree drift:

- `services/` is a root-level mirror of `app/services/`
- `models/` is a root-level mirror of `app/models/`
- `etenders_acquisition/` contains a separate experimental stack
- `frontend/` contains the active Vite app, while `frontend/command-centre/` appears partially populated and the compose files reference a missing `frontend/command-centre/Dockerfile`

## 1. Top-Level Folders

| Folder | Classification | Notes |
| --- | --- | --- |
| `.git` | ACTIVE | Git metadata |
| `.github` | ACTIVE | CI/workflow metadata |
| `.pycache` | ARCHIVE_CANDIDATE | Generated Python cache |
| `.pytest_cache` | ARCHIVE_CANDIDATE | Generated pytest cache |
| `Word Recovery` | ARCHIVE_CANDIDATE | Non-runtime recovery artifacts |
| `app` | ACTIVE | Primary Python application package |
| `backups` | ARCHIVE_CANDIDATE | Backup material, not runtime source |
| `data` | UNKNOWN | Present, but not clearly established as authoritative runtime storage |
| `deploy` | ACTIVE | Deployment-related assets |
| `docker` | ACTIVE | Prometheus/Grafana and container support files |
| `docs` | ACTIVE | Operational and engineering documentation |
| `etenders_acquisition` | EXPERIMENTAL | Separate stack with its own API, DB, compose file, and frontend |
| `frontend` | ACTIVE | Active Vite/React frontend tree |
| `generated` | ACTIVE | Generated output directory used by the system |
| `models` | DUPLICATE | Duplicates `app/models` 1:1 |
| `monthly_quotes` | ACTIVE | Runtime/static output mounted by the main app |
| `nginx` | ACTIVE | Frontend/proxy config for production compose |
| `runtime` | ACTIVE | Main runtime state, artifacts, logs, proofs, queues, profiles |
| `scripts` | ACTIVE | Operational scripts, local startup, validation, worker startup |
| `services` | DUPLICATE | Large mirror of `app/services`; overlap scan found `259` shared Python files and `0` root-only files |
| `tests` | ACTIVE | Test suite |

## 2. All `package.json` Files

| Path | Classification | Notes |
| --- | --- | --- |
| `frontend/package.json` | ACTIVE | Vite + React frontend; scripts: `dev`, `build`, `lint`, `preview` |
| `etenders_acquisition/lmcp-dashboard/package.json` | EXPERIMENTAL | Separate Next.js dashboard inside the experimental `etenders_acquisition` stack |

## 3. All Python Entrypoints

Definition used here: Python files with a direct `if __name__ == "__main__"` block, plus production module entrypoints used by `uvicorn`/Celery.

### Production module entrypoints

| Path | Classification | Notes |
| --- | --- | --- |
| `app/main.py` | ACTIVE | Main FastAPI app used by compose and startup scripts |
| `app/celery_app.py` | ACTIVE | Celery worker/beat app used by production workers |
| `app/recovery_main.py` | EXPERIMENTAL | Alternate FastAPI startup path; not referenced by main compose |
| `etenders_acquisition/api/main.py` | EXPERIMENTAL | Separate FastAPI app for experimental acquisition stack |
| `etenders_acquisition/main.py` | EXPERIMENTAL | Separate orchestrator entrypoint |

### Root-level direct execution entrypoints

- `backfill_submission_profit.py`
- `probe_etenders.py`

### `scripts/` direct execution entrypoints

- `scripts/approve_manual_pilot.py`
- `scripts/approve_workspace_pilot.py`
- `scripts/analyze_http_failures.py`
- `scripts/audit_etenders_harvest_rejection.py`
- `scripts/audit_write_probe.py`
- `scripts/backend_watchdog.py`
- `scripts/bootstrap_initial_auth_users.py`
- `scripts/bootstrap_remaining_live_queue_candidates.py`
- `scripts/build_source_maintenance_action_list.py`
- `scripts/check_controlled_operation_readiness.py`
- `scripts/check_local_system.py`
- `scripts/check_operations_worker_ready.py`
- `scripts/classify_harvest_effectiveness_sources.py`
- `scripts/daily_supervised_production_ritual.py`
- `scripts/extract_rfq_items.py`
- `scripts/fresh_live_rfq_backend_smoke_batch.py`
- `scripts/fresh_live_rfq_backend_smoke_test.py`
- `scripts/historical_rfq_volume_report.py`
- `scripts/live_backend_uptime_check.py`
- `scripts/live_queue_status.py`
- `scripts/local_api_session.py`
- `scripts/normalize_live_queue_candidates.py`
- `scripts/prune_completed_live_queue_candidates.py`
- `scripts/record_manual_submission_proof.py`
- `scripts/repair_invalid_pdf_artifacts.py`
- `scripts/repair_refresh_bundle_source_artifacts.py`
- `scripts/repair_zero_pricing_bundles.py`
- `scripts/review_submission_pack.py`
- `scripts/run_daily_pilot_loop.py`
- `scripts/run_etenders_auto_harvest_recovery.py`
- `scripts/run_etenders_connectivity_diagnostics.py`
- `scripts/run_etenders_fetch_diagnostics.py`
- `scripts/run_fixture_backed_fresh_intake.py`
- `scripts/run_harvest_effectiveness_sprint7.py`
- `scripts/run_manual_pilot.py`
- `scripts/run_simulation_harness.py`
- `scripts/run_supervised_pilot_week.py`
- `scripts/run_weekly_dry_dispatch_cycle.py`
- `scripts/run_workspace_pilot.py`
- `scripts/run_workspace_pilot_batch.py`
- `scripts/seed_demo_live_rfq_bundle.py`
- `scripts/show_manual_pilot_report.py`
- `scripts/supplier_quote_live_imap_happy_path.py`

### `app/` direct execution entrypoints

- `app/init_db.py`
- `app/registry_enricher.py`
- `app/reset_db.py`
- `app/seed_markup_rules.py`
- `app/seed_supplier_items.py`
- `app/seed_suppliers.py`
- `app/source_health.py`
- `app/harvester.py`
- `app/parser_router.py`
- `app/email_rfq_report.py`

### `app/scripts/` direct execution entrypoints

- `app/scripts/manual_review_backup.py`
- `app/scripts/portal_radar_diagnostic.py`
- `app/scripts/run_acquirable_live_rfq_promotion.py`
- `app/scripts/run_acquisition_backed_validation.py`
- `app/scripts/run_csd_report_refresh.py`
- `app/scripts/run_manual_review_pilot.py`
- `app/scripts/run_national_portal_radar.py`
- `app/scripts/run_scheduled_tender_harvest.py`
- `app/scripts/run_source_by_source_live_smoke.py`
- `app/scripts/seed_supplier_products.py`

### Service/utility direct execution entrypoints

These are runnable utility/service modules, but they are not the official runtime entrypoint:

- `services/amount_quantity_integrity_validation_engine.py`
- `services/auto_multi_form_pipeline.py`
- `services/auto_profile_generator.py`
- `services/buyer_form_population_service.py`
- `services/buyer_pdf_renderer_form_filler_service.py`
- `services/buyer_pricing_schedule_filler_service.py`
- `services/buyer_pricing_schedule_mapper_service.py`
- `services/boq_row_routing_service.py`
- `services/column_realignment_engine.py`
- `services/continuation_merge_repair_engine.py`
- `services/csd_monthly_refresh_service.py`
- `services/direct_portal_harvesters.py`
- `services/document_ingestion_service.py`
- `services/etenders_playwright.py`
- `services/final_boq_row_normalization_engine.py`
- `services/final_output_builder_service.py`
- `services/handwriting_field_detector_service.py`
- `services/handwriting_full_auto_service.py`
- `services/handwriting_signature_engine.py`
- `services/handwriting_simulation_service.py`
- `services/harvest_source_registry_service.py`
- `services/quote_pricing_engine_service.py`
- `services/sbd_auto_completion_service.py`
- `services/stamp_service.py`
- `app/services/amount_quantity_integrity_validation_engine.py`
- `app/services/auto_multi_form_pipeline.py`
- `app/services/auto_profile_generator.py`
- `app/services/boq_row_routing_service.py`
- `app/services/buyer_form_population_service.py`
- `app/services/buyer_pdf_renderer_form_filler_service.py`
- `app/services/buyer_pricing_schedule_filler_service.py`
- `app/services/buyer_pricing_schedule_mapper_service.py`
- `app/services/column_realignment_engine.py`
- `app/services/continuation_merge_repair_engine.py`
- `app/services/csd_monthly_refresh_service.py`
- `app/services/direct_portal_harvesters.py`
- `app/services/document_ingestion_service.py`
- `app/services/etenders_playwright.py`
- `app/services/final_boq_row_normalization_engine.py`
- `app/services/final_output_builder_service.py`
- `app/services/handwriting_field_detector_service.py`
- `app/services/handwriting_full_auto_service.py`
- `app/services/handwriting_signature_engine.py`
- `app/services/handwriting_simulation_service.py`
- `app/services/harvest_source_registry_service.py`
- `app/services/quote_pricing_engine_service.py`
- `app/services/sbd_auto_completion_service.py`
- `app/services/stamp_service.py`

## 4. All FastAPI Entrypoints

Definition used here: files that instantiate a `FastAPI(...)` application object, not individual `APIRouter` modules.

| Path | Classification | Notes |
| --- | --- | --- |
| `app/main.py` | ACTIVE | Official FastAPI app. Compose and startup scripts point here via `LMCP_APP_ENTRYPOINT` |
| `app/recovery_main.py` | EXPERIMENTAL | Alternate app factory path; not referenced by main runtime |
| `etenders_acquisition/api/main.py` | EXPERIMENTAL | Separate API for experimental acquisition stack |
| `app/main.py.backup_v50_7` | ARCHIVE_CANDIDATE | Backup app entrypoint |
| `app/main.py.bak_mission_control_compat` | ARCHIVE_CANDIDATE | Backup app entrypoint |
| `app/main.py.bak_pipeline_sync_20260503_003929` | ARCHIVE_CANDIDATE | Backup app entrypoint |
| `app/main.py.bak_proof_history_20260503_095829` | ARCHIVE_CANDIDATE | Backup app entrypoint |
| `app/main.py.bak_proof_submission_20260503_004609` | ARCHIVE_CANDIDATE | Backup app entrypoint |
| `app/main.py.bak_submission_history_recent_20260502_180537` | ARCHIVE_CANDIDATE | Backup app entrypoint |
| `app/main.py.bak_submission_history_recent_20260502_180546` | ARCHIVE_CANDIDATE | Backup app entrypoint |
| `app/main.py.bak_submission_history_recent_20260502_181529` | ARCHIVE_CANDIDATE | Backup app entrypoint |

Note: `app/api/*.py`, `app/api.py`, `app/audit_api.py`, `app/compliance_api.py`, `app/dashboard_api.py`, `app/email_api.py`, `app/harvester_api.py`, `app/opportunities_api.py`, `app/quote_api.py`, `app/quote_pack_api.py`, `app/quotes_api.py`, `app/relevance_api.py`, `app/sbd_api.py`, `app/submission_api.py`, `app/system_guard_api.py`, `app/tasks_api.py`, `app/ui.py`, and `app/ui_routes.py` are router modules, not standalone FastAPI app entrypoints.

## 5. All Frontend Apps

| Path | Classification | Notes |
| --- | --- | --- |
| `frontend/` | ACTIVE | Main frontend package. Vite + React app with `frontend/package.json`, `frontend/index.html`, `frontend/vite.config.js`, `frontend/src/` |
| `frontend/command-centre/` | EXPERIMENTAL | Partial TypeScript subtree exists, but there is no `package.json` or `Dockerfile` in this folder even though compose references `frontend/command-centre/Dockerfile` |
| `etenders_acquisition/lmcp-dashboard/` | EXPERIMENTAL | Separate Next.js dashboard tied to the experimental acquisition stack |

## 6. All Worker Scripts

### Active worker/runtime definitions

| Path | Classification | Notes |
| --- | --- | --- |
| `app/celery_app.py` | ACTIVE | Defines Celery broker, queues, routes, beat schedule, and autodiscovery |
| `app/tasks/__init__.py` | ACTIVE | Task package |
| `app/tasks/csd_monthly_refresh_task.py` | ACTIVE | Celery task module |
| `app/tasks/submission_scheduler_tasks.py` | ACTIVE | Celery task module |
| `scripts/start_production_workers.sh` | ACTIVE | Starts default worker, operations worker, and beat |
| `scripts/check_operations_worker_ready.py` | ACTIVE | Worker readiness probe used by startup |
| `scripts/ops/production_start.sh` | ACTIVE | Starts the backend API with `uvicorn` |
| `scripts/start_local_manual_production.sh` | ACTIVE | Local manual-production runtime launcher |

### Runtime processes referenced by production compose

- `backend`: `uvicorn ${LMCP_APP_ENTRYPOINT:-app.main:app}`
- `worker`: `celery -A app.celery_app.celery_app worker`
- `operations-worker`: `celery -A app.celery_app.celery_app worker --queues=operations_queue`
- `beat`: `celery -A app.celery_app.celery_app beat`

## 7. All Database/Config Files

### Root-level config files

- `.env`
- `.env.example`
- `.env.production`
- `.env.production.example`
- `Dockerfile`
- `docker-compose.yml`
- `docker-compose.production.yml`
- `pytest.ini`
- `requirements.txt`
- `Makefile`
- `api.json`
- `openapi.json`

### Subproject config files

- `frontend/.env`
- `frontend/package.json`
- `frontend/vite.config.js`
- `frontend/tsconfig.json`
- `etenders_acquisition/.env`
- `etenders_acquisition/docker-compose.yml`
- `etenders_acquisition/lmcp-dashboard/package.json`
- `etenders_acquisition/lmcp-dashboard/next.config.ts`
- `etenders_acquisition/lmcp-dashboard/tsconfig.json`

### Database/state files found at repo level

- `celerybeat-schedule.db`
- `celerybeat-schedule.db.db`
- `runtime/celerybeat-schedule.db`
- `runtime/harvest.db`
- `etenders_acquisition/etenders.db`

### Config folders

- `docker/`
- `deploy/`
- `nginx/`

## 8. All Generated/Runtime Folders

### Generated

- `generated/quotation_packs`

### Monthly quote output

- `monthly_quotes/2026-06`

### Runtime top-level folders

- `runtime/ai_tender_adjudication`
- `runtime/ajax_tender_feed`
- `runtime/audit_trail`
- `runtime/auth`
- `runtime/autonomous_cycle`
- `runtime/autonomous_procurement_execution`
- `runtime/award_prediction`
- `runtime/backups`
- `runtime/bid_defense`
- `runtime/bid_margin_strategy`
- `runtime/bid_strategy`
- `runtime/boq_intelligence`
- `runtime/browser_acquisition`
- `runtime/buyer_intelligence`
- `runtime/category_fallback_estimator`
- `runtime/chrome-profile`
- `runtime/clickable_navigation_v40`
- `runtime/commercial_intelligence`
- `runtime/commercial_risk_heatmap`
- `runtime/compliance`
- `runtime/controlled_validation`
- `runtime/csd_monthly_refresh`
- `runtime/debug`
- `runtime/decision_intelligence`
- `runtime/discovery_memory`
- `runtime/document_intelligence`
- `runtime/downloaded_tender_documents`
- `runtime/e2e_fixtures`
- `runtime/etenders_direct`
- `runtime/etenders_session`
- `runtime/execution_evidence`
- `runtime/exports`
- `runtime/fetch-failures`
- `runtime/final_automation`
- `runtime/final_bid_pricing`
- `runtime/final_download_interceptor_downloads`
- `runtime/final_submission_v47_5`
- `runtime/final_tender_submission`
- `runtime/generated_forms`
- `runtime/go_live_guards`
- `runtime/handwriting_simulation`
- `runtime/harvest_effectiveness`
- `runtime/harvest_recovery`
- `runtime/harvest_runs`
- `runtime/health`
- `runtime/historical_price_estimator`
- `runtime/live_browser_attach_v47_3`
- `runtime/live_buyer_packs`
- `runtime/live_supplier_responses`
- `runtime/locks`
- `runtime/logs`
- `runtime/manual_production`
- `runtime/manual_review`
- `runtime/mission_control`
- `runtime/multi_portal_discovery`
- `runtime/operator_actions`
- `runtime/operator_auth`
- `runtime/opportunity_extraction`
- `runtime/pilot_runs`
- `runtime/pipeline_enforcement`
- `runtime/playwright`
- `runtime/playwright_profiles`
- `runtime/portal_fetch`
- `runtime/portal_submission`
- `runtime/portal_uploads`
- `runtime/pricing_engine`
- `runtime/pricing_summaries`
- `runtime/procurement_category_ai`
- `runtime/procurement_negotiation_intelligence`
- `runtime/production_lock`
- `runtime/proof_center`
- `runtime/pycache`
- `runtime/quote_compilation`
- `runtime/radar_cycles`
- `runtime/rate_sanity`
- `runtime/real_profit_pricing`
- `runtime/retry_engine`
- `runtime/review_quarantine`
- `runtime/review_queue`
- `runtime/rfq_boq_extraction`
- `runtime/rfq_document_acquisition`
- `runtime/rfq_document_intelligence`
- `runtime/rfq_docx_main_document_intelligence`
- `runtime/rfq_lifecycle`
- `runtime/rfq_packs`
- `runtime/rfq_zip_content_extraction`
- `runtime/safe_autonomous_scheduler`
- `runtime/sbd_completion`
- `runtime/security`
- `runtime/simulation_runs`
- `runtime/sku_pricing_booster`
- `runtime/smart_upload_v47_4`
- `runtime/source_packs`
- `runtime/sprint_7`
- `runtime/submission_history`
- `runtime/submission_pack`
- `runtime/submission_packages`
- `runtime/submission_proofs`
- `runtime/submission_scheduler`
- `runtime/supervisor`
- `runtime/supplier_expansion`
- `runtime/supplier_learning`
- `runtime/supplier_market_intelligence`
- `runtime/supplier_matching`
- `runtime/supplier_outreach_emails`
- `runtime/supplier_price_memory`
- `runtime/supplier_quote_adjudication`
- `runtime/supplier_quote_auto_ingestion`
- `runtime/supplier_quote_ingestion`
- `runtime/supplier_quote_intelligence`
- `runtime/supplier_quotes`
- `runtime/support_document_resolution`
- `runtime/system_control`
- `runtime/system_state`
- `runtime/tender_form_intelligence`
- `runtime/tender_radar`
- `runtime/tender_submission_pipeline`
- `runtime/tmp`
- `runtime/tmp_e2e_real_pilot_facility_supplies`
- `runtime/tmp_e2e_real_pilot_office_consumables`
- `runtime/tmp_e2e_real_pilot_store_replenishment`
- `runtime/tmp_e2e_valid_supply_delivery`
- `runtime/v31_smart_harvester`
- `runtime/v32_real_rfq_harvester`
- `runtime/v33_real_portal_extraction`
- `runtime/v34_structured_rfq_extractor`
- `runtime/v35_playwright_live_dom`
- `runtime/v36_interactive_playwright`
- `runtime/v37_deep_rfq_link_extractor`
- `runtime/v38_interactive_click_deep_extraction`
- `runtime/v39_true_navigation_extraction`
- `runtime/watchdog`

## 9. Classification Notes

### ACTIVE

Use this for the main application path and runtime-critical assets:

- `app/`
- `frontend/`
- `runtime/`
- `generated/`
- `monthly_quotes/`
- `docker/`
- `deploy/`
- `nginx/`
- `scripts/`
- `tests/`
- `docs/`

### DUPLICATE

Use this for mirrored trees that should not both be treated as authoritative:

- `services/` duplicates `app/services/`
- `models/` duplicates `app/models/`

### EXPERIMENTAL

Use this for stacks that look separate, incomplete, or not wired into the main runtime:

- `etenders_acquisition/`
- `frontend/command-centre/`
- `app/recovery_main.py`
- `etenders_acquisition/api/main.py`
- `etenders_acquisition/main.py`

### ARCHIVE_CANDIDATE

Use this for caches, backups, recovery artifacts, and backup app entrypoints:

- `.pycache/`
- `.pytest_cache/`
- `Word Recovery/`
- `backups/`
- `app/main.py.backup_v50_7`
- `app/main.py.bak_*`

### UNKNOWN

Use this where the folder exists but the current authoritative role is not yet explicit:

- `data/`

## 10. Recommendation For The Official Runtime

The official runtime should be treated as:

1. Backend API: `app.main:app`
2. Worker/beat runtime: `app.celery_app.celery_app`
3. Container orchestration:
   - `docker-compose.production.yml` for the official supervised/production runtime
   - `docker-compose.yml` for local/dev runtime
4. Runtime state root: `runtime/`
5. Static/generated outputs:
   - `monthly_quotes/`
   - `generated/`
   - mounted runtime static paths exposed by `app/main.py`

### Practical interpretation for stabilization work

- Treat `app/` as the only authoritative backend source tree.
- Treat `app/services/` as authoritative over root `services/`.
- Treat `app/models/` as authoritative over root `models/`.
- Treat `frontend/` as the current official frontend package because it has the active `package.json` and build files.
- Treat `frontend/command-centre/` as incomplete until it has its own full build definition or the compose files are corrected.
- Do not treat `etenders_acquisition/` as part of the official LMCP AutoQuote runtime unless explicitly promoted later.

### Immediate stabilization concern

`docker-compose.yml` and `docker-compose.production.yml` both reference `frontend/command-centre/Dockerfile`, but this file was not found during the audit. The backend runtime path is clear; the frontend runtime path is not yet consistent with the current filesystem.
