# Intelligence Migration Report

Date: 2026-06-22
Scope: first controlled intelligence extraction into `lmcp-core/services/intelligence/`

## Objective

Create the initial `lmcp-core` intelligence landing zone without breaking:

- `app.main:app`
- `/health`
- `/status`
- current parsing and pricing queue behavior
- current extraction runtime paths
- existing imports and API routes

## Intelligence Source Assets

The current intelligence surface includes:

- BOQ extraction and normalization
- PDF, DOCX, spreadsheet, and ZIP parsing
- document intelligence and structured RFQ extraction
- pricing-table extraction and table reconstruction
- field extraction and tender-form intelligence
- handwriting and glyph processing utilities
- extraction validation and sanity logic

Primary live source modules:

- `app/services/document_ingestion_service.py`
- `app/services/rfq_document_intelligence.py`
- `app/services/rfq_docx_main_document_intelligence.py`
- `app/services/rfq_boq_extraction_engine.py`
- `app/services/rfq_zip_content_extraction_engine.py`
- `app/services/structured_rfq_extractor_v34_service.py`
- `app/services/pricing_table_extraction_v42_service.py`
- `app/services/final_boq_row_normalization_engine.py`
- `app/services/amount_quantity_integrity_validation_engine.py`
- `app/services/parser_executor_service.py`

## Active Extraction Entrypoints

Active task and orchestration entrypoints:

- `app.tasks.rfq_lifecycle_parsing_task`
- `app.tasks.rfq_lifecycle_pricing_task`
- `app.services.rfq_lifecycle_service.RfqLifecycleService.advance_discovered`
- `app.services.rfq_lifecycle_service.RfqLifecycleService.advance_parsed`

Active API entrypoints:

- `app/api/backend_intelligence_api.py`
- `app/api/decision_intelligence_api.py`
- `app/api/structured_rfq_extractor_v34_api.py`
- `app/api/pricing_table_extraction_v42_api.py`
- `app/api/tender_form_intelligence_api.py`
- `app/api/sbd_intelligence_api.py`
- handwriting and deep-extraction APIs under `app/api/*`

## Celery Task Ownership

Current queue ownership is shared with the lifecycle runtime:

- `parsing_queue`
  - exposed by `app.tasks.rfq_lifecycle_parsing_task`
  - actual parsing is still executed inside `RfqLifecycleService.advance_discovered`
- `pricing_queue`
  - exposed by `app.tasks.rfq_lifecycle_pricing_task`
  - current handoff mixes intelligence-readiness with downstream pricing progression

Intelligence is therefore not yet an isolated worker boundary. Queue ownership is logical, but execution still flows through the monolithic lifecycle service.

## Database Ownership Targets

Canonical target ownership for Intelligence Service should include:

- document intelligence results
- BOQ extraction jobs
- normalized BOQ rows
- buyer events
- buyer profiles
- procurement signals

Current actual ownership is still split across:

- SQLAlchemy buyer-intelligence models
- acquisition-side BOQ models in the separate `etenders_acquisition` lineage
- filesystem-backed JSON artifacts in `runtime/*`

## Filesystem and Runtime Dependencies

The current intelligence surface depends directly on:

- `runtime/document_intelligence/`
- `runtime/boq_intelligence/`
- `runtime/rfq_boq_extraction/`
- `runtime/rfq_document_intelligence/`
- `runtime/rfq_docx_main_document_intelligence/`
- `runtime/rfq_zip_content_extraction/`
- `runtime/tender_form_intelligence/`
- `runtime/v34_structured_rfq_extractor/`
- `runtime/v37_deep_rfq_link_extractor/`
- `runtime/v38_interactive_click_deep_extraction/`
- `runtime/v39_true_navigation_extraction/`
- `runtime/downloaded_tender_documents/`
- `runtime/support_document_resolution/`

## OCR, PDF, and Runtime Requirements

The current intelligence runtime depends on a mixed local tooling stack, including:

- `PyPDF2`
- `PyMuPDF` via `fitz`
- `pdfplumber`
- `python-docx`
- `openpyxl`
- `Pillow`

These dependencies are used opportunistically inside live services rather than through a single isolated parser runtime. That makes extraction-tool behavior sensitive to local environment differences.

## Coupling Risks

The main coupling risks that still block direct source relocation are:

- parsing and extraction are orchestrated inside `rfq_lifecycle_service` rather than through a clean intelligence boundary
- runtime artifacts are written into many `runtime/*` directories directly from parser services
- BOQ, validation, and readiness logic partially overlap with acquisition ingress and downstream commercial gating
- handwriting and document utilities are exposed through the shared API tree and may also serve submission-era document preparation paths
- parser selection, confidence scoring, and artifact grouping remain embedded in live Python modules rather than boundary-owned config

## Unsafe Shared State

The current unsafe shared-state patterns include:

- filesystem-backed extraction summaries used as operational state
- shared runtime folders consumed by acquisition, intelligence, and commercial flows
- queue ownership that is documented logically but executed inside shared lifecycle orchestration
- duplicated persistence split across SQLAlchemy, SQLite-adjacent models, and JSON artifacts

## Future Extraction Order

Recommended intelligence extraction order:

1. Extract intelligence-owned documentation and static config contracts first.
2. Extract read-only parser-routing and normalization helpers behind compatibility wrappers.
3. Extract runtime path adapters for document-intelligence and BOQ artifacts.
4. Extract parser execution helpers after dependency requirements are made explicit and stable.
5. Extract lifecycle-facing orchestration and API routers last, after queue and persistence ownership are isolated.

Modules that should wait:

- `app/services/rfq_document_intelligence.py`
- `app/services/rfq_boq_extraction_engine.py`
- `app/services/rfq_docx_main_document_intelligence.py`
- `app/services/structured_rfq_extractor_v34_service.py`
- `app/services/pricing_table_extraction_v42_service.py`
- `app/services/rfq_lifecycle_service.py`

## What Was Migrated

The migration was intentionally limited to intelligence-owned documentation and target scaffolding:

- updated `lmcp-core/services/intelligence/README.md`
- created `lmcp-core/services/intelligence/docs/SOURCE_MAP.md`
- created `lmcp-core/services/intelligence/runtime/README.md`
- created `lmcp-core/services/intelligence/configs/README.md`

This establishes the `lmcp-core` target boundary for intelligence without changing runtime behavior.

## Rollback Instructions

This migration is documentation-only and can be rolled back without runtime impact by removing:

- `lmcp-core/services/intelligence/docs/SOURCE_MAP.md`
- `lmcp-core/services/intelligence/runtime/README.md`
- `lmcp-core/services/intelligence/configs/README.md`
- the updated content in `lmcp-core/services/intelligence/README.md`
- `docs/INTELLIGENCE_MIGRATION_REPORT.md`

No backend imports, API routes, task registration, runtime files, or compose files were changed in this step.
