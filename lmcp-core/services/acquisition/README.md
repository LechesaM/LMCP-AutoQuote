# Acquisition Service

`lmcp-core/services/acquisition/` is the target home for tender discovery, portal harvesting, external document acquisition, and source-health supervision.

## Ownership

This service boundary owns:

- tender harvesting and opportunity discovery
- eTenders and portal scraping
- Playwright navigation and session-backed browser acquisition
- source registry, source selection, and fetch diagnostics
- retry and backoff behavior for acquisition-side failures
- incremental harvesting and scheduled harvest cycles
- buyer-pack and supporting document downloading

## Current Runtime Sources

The active acquisition runtime still lives in the current backend tree. Primary source modules include:

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
- `app/services/autonomous_tender_hunter.py`
- `app/tasks.py`

## Migration Posture

This controlled migration does not move any live Python acquisition module. It establishes the `lmcp-core` landing zone and centralizes migration documentation while preserving:

- `app.main:app` as the official backend entrypoint
- existing router registration
- existing Celery task names and queue ownership
- existing runtime directory paths

## Subdirectories

- `docs/`
  - acquisition source maps and migration references
- `runtime/`
  - future home for acquisition-owned runtime metadata after compatibility work is complete
- `configs/`
  - future home for acquisition-owned static configuration once it can be separated safely from the live runtime

## Out of Scope

This boundary does not yet absorb:

- pricing or quote-generation logic
- submission execution logic
- frontend assets
- governance controls outside acquisition-specific source health and fetch supervision
