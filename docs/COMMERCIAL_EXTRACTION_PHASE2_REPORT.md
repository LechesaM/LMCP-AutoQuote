# Commercial Extraction Phase 2 Report

Date: 2026-06-22
Scope: second controlled commercial extraction into `lmcp-core/services/commercial/`

## Objective

Relocate low-risk commercial utilities without changing:

- backend entrypoint authority
- API routes
- runtime behavior
- Celery orchestration
- pricing/adjudication workflow ownership
- submission logic

## Files Moved

The following isolated commercial utility implementations were relocated into `lmcp-core/services/commercial/`:

- `app/services/profitability.py` implementation moved to `lmcp-core/services/commercial/profitability.py`
- `app/services/quote_pricing_engine_service.py` implementation moved to `lmcp-core/services/commercial/quote_pricing_engine_service.py`

## Compatibility Shims Added

The original import paths were preserved by converting the original `app/services/*` modules into thin compatibility wrappers that dynamically load the relocated implementation files:

- `app/services/profitability.py`
- `app/services/quote_pricing_engine_service.py`

## Imports Preserved

Existing imports continue to work unchanged, including:

- `from app.services.profitability import calculate_profitability`
- `from app.services.profitability import profitability_decision`
- `from app.services.profitability import evaluate_pricing_result_profitability`
- `from app.services.quote_pricing_engine_service import attach_quote_pricing_to_record`
- `from app.services.quote_pricing_engine_service import price_buyer_schedule_rows`

No API module, router, or test import path was changed.

## Why These Utilities Were Chosen

These utilities were selected because they are commercial-owned helpers with narrow responsibilities:

- profitability math and pricing-result extraction
- buyer schedule row pricing and record enrichment

They do not directly orchestrate adjudication engines, pricing pipelines, RFQ lifecycle transitions, review queues, or final submission compilation.

## What Was Intentionally Not Moved

The following were intentionally left in place because they remain more tightly coupled:

- `app/services/pricing_engine.py`
- `app/services/pricing_engine_v2_realistic.py`
- `app/services/real_profit_pricing_service.py`
- `app/services/quote_engine.py`
- `app/services/quote_pack_service.py`
- `app/services/quote_pack_builder_service.py`
- `app/services/quote_review_service.py`
- `app/services/supplier_quote_comparison_service.py`
- `app/services/supplier_award_execution_service.py`
- `app/services/tender_pipeline.py`
- any Celery task modules
- any submission-trigger modules

`quote_pricing_engine_service.py` was considered safe because it only enriches in-memory records and does not alter workflow state or execute pricing orchestration.

## Remaining Coupling Risks

The extracted utilities still depend on active runtime modules and are not yet standalone platform services.

Key remaining risks:

- `profitability.py` remains a helper used by broader pricing logic and has not been detached from the commercial namespace entirely
- `quote_pricing_engine_service` is still used by `document_ingestion_service`
- the `lmcp-core` directory is a filesystem destination, not a normal Python package import path, so wrappers are still required
- the full pricing, adjudication, and quote generation pipelines remain in the active runtime tree

## Rollback Instructions

To roll back this extraction safely:

1. Restore the original implementation code into:
   - `app/services/profitability.py`
   - `app/services/quote_pricing_engine_service.py`
2. Remove the relocated implementation files:
   - `lmcp-core/services/commercial/profitability.py`
   - `lmcp-core/services/commercial/quote_pricing_engine_service.py`
3. Remove this report if the extraction is being fully reverted:
   - `docs/COMMERCIAL_EXTRACTION_PHASE2_REPORT.md`

No import call sites, routes, or worker entrypoints need to be reverted because they were not changed.
