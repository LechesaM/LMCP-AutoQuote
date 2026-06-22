# Acquisition Extraction Phase 2 Report

Date: 2026-06-22
Scope: second controlled acquisition extraction into `lmcp-core/services/acquisition/`

## Objective

Relocate the next safest acquisition helpers without changing:

- backend entrypoint authority
- API routes
- runtime behavior
- browser automation
- Celery orchestration
- tender, pricing, or submission workflows

## Files Moved

The following isolated acquisition utility implementations were relocated into `lmcp-core/services/acquisition/`:

- `app/services/harvest_source_registry_service.py` implementation moved to `lmcp-core/services/acquisition/harvest_source_registry_service.py`
- `app/services/portal_crawl_priority.py` implementation moved to `lmcp-core/services/acquisition/portal_crawl_priority.py`

## Compatibility Shims Added

The original import paths were preserved by converting the original `app/services/*` modules into thin compatibility wrappers that dynamically load the relocated implementation files:

- `app/services/harvest_source_registry_service.py`
- `app/services/portal_crawl_priority.py`

## Imports Preserved

Existing imports continue to work unchanged, including:

- `from app.services.harvest_source_registry_service import get_curated_live_source_file`
- `from app.services.harvest_source_registry_service import load_harvest_sources`
- `from app.services.harvest_source_registry_service import build_default_harvest_sources`
- `from app.services.portal_crawl_priority import choose_portals_for_harvest`

No API module, router, or test import path was changed.

## Why These Utilities Were Chosen

These utilities were selected because they are acquisition-owned helpers with narrow responsibilities:

- source registry normalization and curated-source selection
- portal crawl prioritization based on static historical stats

They do not directly orchestrate Playwright, Celery tasks, extraction, pricing, or submission workflows.

## Remaining Coupling Risks

The extracted utilities still depend on live runtime modules and are not yet standalone platform services.

Key remaining risks:

- `harvest_source_registry_service` still depends on `app.services.portal_registry` for the portal metadata source
- `portal_crawl_priority` still depends on `app.services.procurement_heatmap`
- the `lmcp-core` directory is a filesystem destination, not a normal Python package import path, so wrappers are still required
- the main harvester, Playwright automation, and Celery orchestration remain in the active runtime tree

## What Was Intentionally Not Moved

The following were intentionally left in place because they remain more tightly coupled:

- `app/services/tender_harvester.py`
- `app/services/local_harvest_service.py`
- `app/services/harvest_scheduler_service.py`
- `app/services/source_parser_routing_service.py`
- `app/services/portal_registry.py`
- `app/services/procurement_heatmap.py`
- Playwright/browser automation modules
- Celery task/orchestration modules

## Rollback Instructions

To roll back this extraction safely:

1. Restore the original implementation code into:
   - `app/services/harvest_source_registry_service.py`
   - `app/services/portal_crawl_priority.py`
2. Remove the relocated implementation files:
   - `lmcp-core/services/acquisition/harvest_source_registry_service.py`
   - `lmcp-core/services/acquisition/portal_crawl_priority.py`
3. Remove this report if the extraction is being fully reverted:
   - `docs/ACQUISITION_EXTRACTION_PHASE2_REPORT.md`

No import call sites, routes, or worker entrypoints need to be reverted because they were not changed.
