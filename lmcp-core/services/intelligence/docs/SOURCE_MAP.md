# Intelligence Source Map

This source map identifies the current runtime assets that belong logically to the Intelligence Service boundary.

## Primary Document Intelligence Modules

- `app/services/document_ingestion_service.py`
- `app/services/rfq_document_intelligence.py`
- `app/services/rfq_docx_main_document_intelligence.py`
- `app/services/rfq_zip_content_extraction_engine.py`
- `app/services/parser_executor_service.py`
- `app/services/source_parser_routing_service.py`

## BOQ, Table, and Field Extraction

- `app/services/rfq_boq_extraction_engine.py`
- `app/services/final_boq_row_normalization_engine.py`
- `app/services/boq_cleanup_pipeline.py`
- `app/services/boq_row_routing_service.py`
- `app/services/pricing_table_extraction_v42_service.py`
- `app/services/sbd_docx_field_completion_engine.py`
- `app/services/sbd_field_mapping_engine_v20.py`
- `app/services/tender_form_intelligence_engine.py`
- `app/services/tender_form_priority_engine.py`

## Validation and Sanity Gates

- `app/services/amount_quantity_integrity_validation_engine.py`
- `app/services/controlled_validation_service.py`
- `app/services/acquisition_backed_validation_service.py`
- `app/services/validation_readiness_service.py`
- `app/services/rfq_normalizer.py`

## Structured RFQ and Deep Extraction

- `app/services/structured_rfq_extractor_v34_service.py`
- `app/services/deep_rfq_link_extractor_v37_service.py`
- `app/services/interactive_click_deep_extraction_v38_service.py`
- `app/services/true_navigation_extraction_v39_service.py`
- `app/services/navigation_intelligence_v41_service.py`
- `app/services/real_rfq_extractor_v32_service.py`

## Handwriting and Glyph Utilities

- `app/services/handwriting_service.py`
- `app/services/handwriting_glyph_service.py`
- `app/services/handwriting_field_detector_service.py`
- `app/services/handwriting_form_overlay_service.py`
- `app/services/handwriting_full_auto_service.py`
- `app/services/handwriting_signature_engine.py`
- `app/services/handwriting_line_ink_v5.py`
- `app/services/handwriting_pen_flow_v8.py`
- `app/services/handwriting_thickness_normalizer_v7.py`
- `app/services/clean_ink_extraction_v3.py`

## Active Extraction Entrypoints

Active task entrypoints and queue handoffs currently include:

- `app.tasks.rfq_lifecycle_parsing_task`
- `app.tasks.rfq_lifecycle_pricing_task`
- `app.services.rfq_lifecycle_service.RfqLifecycleService.advance_discovered`
- `app.services.rfq_lifecycle_service.RfqLifecycleService.advance_parsed`

Active API surfaces that expose or trigger intelligence behavior include:

- `app/api/backend_intelligence_api.py`
- `app/api/decision_intelligence_api.py`
- `app/api/structured_rfq_extractor_v34_api.py`
- `app/api/pricing_table_extraction_v42_api.py`
- `app/api/tender_form_intelligence_api.py`
- `app/api/sbd_intelligence_api.py`
- handwriting and deep-extraction APIs under `app/api/*`

## Runtime and Filesystem Dependencies

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

## Not Migrated In This Step

These runtime-owned APIs and Python modules remain in place and are not moved in this first intelligence extraction step.
