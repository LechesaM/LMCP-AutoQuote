# Intelligence Service

`lmcp-core/services/intelligence/` is the target home for document understanding, BOQ extraction, parser orchestration, field extraction, and normalization of RFQ content into machine-usable structures.

## Ownership

This service boundary owns:

- BOQ extraction and normalization
- PDF, DOCX, spreadsheet, and ZIP content parsing
- OCR-adjacent and handwriting/glyph extraction utilities
- document intelligence and structured RFQ extraction
- pricing-table extraction and table reconstruction
- field extraction, mapping, and form intelligence
- extraction validation, quantity/integrity checks, and sanity gates

## Current Runtime Sources

The active intelligence runtime still lives in the current backend tree. Primary source modules include:

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
- `app/services/tender_form_intelligence_engine.py`
- `app/services/handwriting_service.py`

## Migration Posture

This controlled migration does not move any live Python extraction module. It establishes the `lmcp-core` landing zone and centralizes migration documentation while preserving:

- `app.main:app` as the official backend entrypoint
- current router registration
- current parsing and pricing queue ownership
- current filesystem-backed extraction artifacts

## Subdirectories

- `docs/`
  - intelligence source maps and migration references
- `runtime/`
  - future home for intelligence-owned extraction artifacts after compatibility work is complete
- `configs/`
  - future home for intelligence-owned static parsing and validation configuration once it can be separated safely

## Out of Scope

This boundary does not yet absorb:

- commercial pricing execution
- quote pack generation
- submission execution logic
- frontend assets
