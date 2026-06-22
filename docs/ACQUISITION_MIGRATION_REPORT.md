# Acquisition Migration Report

Date: 2026-06-22
Scope: first controlled acquisition extraction into `lmcp-core/services/acquisition/`

## Objective

Create the initial `lmcp-core` acquisition landing zone without breaking:

- `app.main:app`
- `/health`
- `/status`
- current Celery task names and queues
- current harvest runtime paths
- existing imports and API routes

## Source Assets Identified

The current acquisition surface includes:

- tender harvesting and multi-portal discovery
- eTenders scraping and session-backed browser navigation
- portal discovery and opportunity extraction
- source registry and source-health tracking
- scheduled harvest execution
- acquisition-side retry and backoff behavior
- buyer-pack and supporting-document download flows

Primary live source modules:

- `app/services/tender_harvester.py`
- `app/services/harvest_scheduler_service.py`
- `app/services/local_harvest_service.py`
- `app/services/harvest_source_registry_service.py`
- `app/services/harvester_adapter.py`
- `app/services/rfq_document_acquisition_engine.py`
- `app/services/etenders_playwright.py`
- `app/services/portal_radar_service.py`
- `app/services/national_portal_radar.py`
- `app/services/source_parser_routing_service.py`

## Active Acquisition Entrypoints

Active task entrypoints:

- `app.tasks.run_supply_intelligence_scan`
- `app.tasks.run_harvest_only`
- `app.tasks.run_harvest_pipeline`
- `app.tasks.run_scheduled_tender_harvest_task`
- `app.tasks.run_rfq_lifecycle_golden_cycle`
- `app.tasks.rfq_lifecycle_acquisition_task`

Active API entrypoints:

- `app/api/opportunities_api.py`
- `app/api/rfq_lifecycle_api.py`
- `app/api/real_rfq_harvester_v32_api.py`
- `app/api/real_portal_rfq_extraction_v33_api.py`
- `app/api/smart_harvester_v31_api.py`
- the versioned `app/api/etenders_*` surfaces

## What Was Migrated

The migration was intentionally limited to acquisition-owned documentation and target scaffolding:

- updated `lmcp-core/services/acquisition/README.md`
- created `lmcp-core/services/acquisition/docs/SOURCE_MAP.md`
- created `lmcp-core/services/acquisition/runtime/README.md`
- created `lmcp-core/services/acquisition/configs/README.md`

This establishes the `lmcp-core` target boundary for acquisition without changing runtime behavior.

## What Was Intentionally Not Migrated

No live Python acquisition module was moved in this first step.

The following remain in place by design:

- all runtime modules under `app/services/*`
- all acquisition-related routers under `app/api/*`
- Celery task definitions in `app/tasks.py`
- runtime files and folders under `runtime/*`
- Playwright session and download state

These assets remain coupled to the active runtime through direct imports, task registration, router registration, and hardcoded runtime paths.

## Coupling Risks

The main coupling risks that still block direct source relocation are:

- `tender_harvester.py` owns a large amount of acquisition orchestration and writes directly into multiple `runtime/*` locations
- eTenders automation is bound to Playwright state, persistent browser profiles, and versioned service modules
- acquisition entrypoints are registered through the active API tree and shared Celery app
- RFQ lifecycle advancement mixes acquisition progression with downstream parsing and pricing handoff
- source-health, discovery, and extraction state is still JSON and file backed rather than boundary-isolated

## Dependency Profile

### Database

- `runtime/harvest.db`
- opportunity and lifecycle persistence paths that remain split across JSON, SQLite, and PostgreSQL-adjacent models

### Celery

- shared `app.celery_app.celery_app`
- `acquisition_queue`
- general harvest tasks under `app/tasks.py`

### Playwright

- `app/services/etenders_playwright.py`
- browser automation helpers in the acquisition service tree
- runtime browser profiles and session captures under `runtime/playwright*`

### Filesystem

- `runtime/live_rfqs.json`
- `runtime/source_health.json`
- `runtime/harvest_runs/`
- `runtime/multi_portal_discovery/`
- `runtime/opportunity_extraction/`
- `runtime/downloaded_tender_documents/`
- `runtime/rfq_document_acquisition/`
- `runtime/portal_fetch/`

### External Portals

- eTenders
- portal-specific harvesters and radar services
- direct buyer and national portal endpoints reached by crawler and browser flows

## Future Extraction Order

Recommended acquisition extraction order:

1. Extract acquisition-owned documentation and static config contracts first.
2. Extract source-registry and read-only source-selection helpers behind compatibility wrappers.
3. Extract runtime path adapters for harvest reports, source health, and discovery outputs.
4. Extract browser/session helpers after Playwright state ownership is explicit.
5. Extract harvest orchestrators and API routers last, after Celery and runtime path compatibility is proven.

Modules that should wait:

- `app/services/tender_harvester.py`
- `app/services/etenders_playwright.py`
- `app/services/harvest_scheduler_service.py`
- `app/services/rfq_document_acquisition_engine.py`
- `app/api/rfq_lifecycle_api.py`

## Rollback Instructions

This migration is documentation-only and can be rolled back without runtime impact by removing:

- `lmcp-core/services/acquisition/docs/SOURCE_MAP.md`
- `lmcp-core/services/acquisition/runtime/README.md`
- `lmcp-core/services/acquisition/configs/README.md`
- the updated content in `lmcp-core/services/acquisition/README.md`
- `docs/ACQUISITION_MIGRATION_REPORT.md`

No backend imports, API routes, Celery registration, runtime files, or compose files were changed in this step.
