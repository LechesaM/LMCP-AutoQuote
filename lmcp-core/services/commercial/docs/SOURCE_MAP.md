# Commercial Source Map

This source map identifies the current runtime assets that belong logically to the Commercial Service boundary.

## Primary Pricing and Quote Modules

- `app/services/pricing_engine.py`
- `app/services/pricing_engine_v2_realistic.py`
- `app/services/real_profit_pricing_service.py`
- `app/services/margin_engine.py`
- `app/services/profitability.py`
- `app/services/quote_engine.py`
- `app/services/quote_engine_service.py`
- `app/services/quote_pricing_engine_service.py`
- `app/services/quote_compilation_service.py`
- `app/services/pricing_schedule_service.py`

## Quote Pack and Review Workflows

- `app/services/quote_pack_service.py`
- `app/services/quote_pack_builder_service.py`
- `app/services/quote_pack_v44_service.py`
- `app/services/tender_quote_pack_generator.py`
- `app/services/quote_review_service.py`
- `app/services/manual_approval_service.py`
- `app/services/quote_draft_store.py`

## Supplier Matching and Adjudication

- `app/services/supplier_engine.py`
- `app/services/supplier_catalog_service.py`
- `app/services/supplier_price_extraction_service.py`
- `app/services/supplier_price_selection_service.py`
- `app/services/supplier_quote_ingestion_service.py`
- `app/services/supplier_quote_comparison_service.py`
- `app/services/supplier_quote_selection_service.py`
- `app/services/supplier_quote_award_service.py`
- `app/services/supplier_award_execution_service.py`
- `app/services/supplier_award_document_service.py`
- `app/services/supplier_reply_matching_service.py`

## RFQ Lifecycle Commercial Coupling

- `app/services/tender_pipeline.py`
- `app/services/intelligence_quote_pipeline.py`
- `app/services/autoquote_pipeline.py`
- `app/services/auto_quote_trigger.py`
- `app/services/auto_quote_trigger_engine.py`
- `app/services/live_autoquote_runner.py`
- `app/services/buyer_pricing_schedule_filler_service.py`
- `app/services/buyer_pricing_schedule_mapper_service.py`

## Active Pricing and Adjudication Entrypoints

Active task and lifecycle entrypoints currently include:

- `app.tasks.rfq_lifecycle_pricing_task`
- `app.services.rfq_lifecycle_service.RfqLifecycleService.advance_parsed`
- manual pricing operations inside `app.services.rfq_lifecycle_service`

Active API surfaces that expose or trigger commercial behavior include:

- `app/api/quote_engine_api.py`
- `app/api/quote_compilation_api.py`
- `app/api/quote_pack_api.py`
- `app/api/quote_pack_v44_api.py`
- `app/api/real_profit_pricing_api.py`
- `app/api/auto_pricing_v43_api.py`
- `app/api/supplier_quotes_api.py`
- `app/api/tender_pipeline_api.py`

## Runtime and Filesystem Dependencies

The current commercial surface depends directly on:

- `runtime/pricing_engine/`
- `runtime/real_profit_pricing/`
- `runtime/final_bid_pricing/`
- `runtime/manual_review/`
- `runtime/review_queue/`
- `runtime/review_quarantine/`
- `runtime/quote_compilation/`
- `runtime/rfq_lifecycle/quote_packs/`
- `runtime/rfq_packs/`
- `runtime/supplier_matching/`
- `runtime/supplier_quote_ingestion/`
- `runtime/supplier_quote_adjudication/`
- `runtime/live_supplier_responses/`
- `runtime/supplier_price_memory/`
- `runtime/manual_production/quote_packs/`

## Not Migrated In This Step

These runtime-owned APIs and Python modules remain in place and are not moved in this first commercial extraction step.
