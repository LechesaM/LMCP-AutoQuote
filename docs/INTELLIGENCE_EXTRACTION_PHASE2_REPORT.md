# Intelligence Extraction Phase 2 Report

Date: 2026-06-22
Scope: second controlled intelligence extraction into `lmcp-core/services/intelligence/`

## Objective

Relocate low-risk intelligence utilities without changing:

- backend entrypoint authority
- API routes
- runtime behavior
- Celery orchestration
- PDF/OCR pipeline ownership
- pricing or submission logic

## Files Moved

The following isolated intelligence utility implementations were relocated into `lmcp-core/services/intelligence/`:

- `app/services/rfq_normalizer.py` implementation moved to `lmcp-core/services/intelligence/rfq_normalizer.py`
- `app/services/amount_quantity_integrity_validation_engine.py` implementation moved to `lmcp-core/services/intelligence/amount_quantity_integrity_validation_engine.py`

## Compatibility Shims Added

The original import paths were preserved by converting the original `app/services/*` modules into thin compatibility wrappers that dynamically load the relocated implementation files:

- `app/services/rfq_normalizer.py`
- `app/services/amount_quantity_integrity_validation_engine.py`

## Imports Preserved

Existing imports continue to work unchanged, including:

- `from app.services.rfq_normalizer import RFQNormalizer`
- `from app.services.amount_quantity_integrity_validation_engine import validate_amount_quantity_integrity`
- `from app.services.amount_quantity_integrity_validation_engine import validate_amount_quantity_integrity_for_table`

No API module, router, or test import path was changed.

## Why These Utilities Were Chosen

These utilities were selected because they are intelligence-owned helpers with narrow responsibilities:

- RFQ normalization into a stable internal shape
- amount/quantity integrity validation for BOQ-style rows

They do not directly orchestrate OCR, Playwright, full document extraction, Celery tasks, pricing execution, or submission workflows.

## What Was Intentionally Not Moved

The following were intentionally left in place because they remain more tightly coupled:

- `app/services/document_ingestion_service.py`
- `app/services/final_boq_row_normalization_engine.py`
- `app/services/boq_row_routing_service.py`
- `app/services/boq_cleanup_pipeline.py`
- OCR engines and PDF extraction pipelines
- any Celery task modules
- any pricing or submission trigger modules

`final_boq_row_normalization_engine.py` was reviewed but not moved in this step because it is closer to the broader BOQ cleanup pipeline than the two extracted helper modules.

## Remaining Coupling Risks

The extracted utilities still depend on active runtime modules and are not yet standalone platform services.

Key remaining risks:

- `RFQNormalizer` is intentionally trivial, but still lives in a workflow-adjacent namespace through the shim
- the validation helper remains logically connected to `boq_cleanup_pipeline`
- document normalization and HTML/link extraction remain in `document_ingestion_service`
- the `lmcp-core` directory is a filesystem destination, not a normal Python package import path, so wrappers are still required
- the full document/PDF/BOQ pipeline and task orchestration remain in the active runtime tree

## Rollback Instructions

To roll back this extraction safely:

1. Restore the original implementation code into:
   - `app/services/rfq_normalizer.py`
   - `app/services/amount_quantity_integrity_validation_engine.py`
2. Remove the relocated implementation files:
   - `lmcp-core/services/intelligence/rfq_normalizer.py`
   - `lmcp-core/services/intelligence/amount_quantity_integrity_validation_engine.py`
3. Remove this report if the extraction is being fully reverted:
   - `docs/INTELLIGENCE_EXTRACTION_PHASE2_REPORT.md`

No import call sites, routes, or worker entrypoints need to be reverted because they were not changed.
