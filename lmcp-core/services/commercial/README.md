# Commercial Service

`lmcp-core/services/commercial/` is the target home for pricing, quote construction, supplier comparison, adjudication, and commercial review workflows.

## Ownership

This service boundary owns:

- pricing engines and margin/profit logic
- supplier matching and supplier quote comparison
- adjudication and supplier award matrix decisions
- quote normalization and quote compilation
- RFQ lifecycle commercial transitions
- manual pricing and review workflows
- approval-ready quote-pack generation
- pricing validation and commercial readiness gates

## Current Runtime Sources

The active commercial runtime still lives in the current backend tree. Primary source modules include:

- `app/services/pricing_engine.py`
- `app/services/pricing_engine_v2_realistic.py`
- `app/services/real_profit_pricing_service.py`
- `app/services/margin_engine.py`
- `app/services/quote_engine.py`
- `app/services/quote_compilation_service.py`
- `app/services/quote_pack_service.py`
- `app/services/quote_pack_builder_service.py`
- `app/services/quote_review_service.py`
- `app/services/manual_approval_service.py`
- `app/services/supplier_quote_comparison_service.py`
- `app/services/supplier_award_execution_service.py`
- `app/services/tender_pipeline.py`

## Migration Posture

This controlled migration does not move any live Python pricing or adjudication module. It establishes the `lmcp-core` landing zone and centralizes migration documentation while preserving:

- `app.main:app` as the official backend entrypoint
- current router registration
- current pricing and retry queue behavior
- current runtime review and pricing artifact paths

## Subdirectories

- `docs/`
  - commercial source maps and migration references
- `runtime/`
  - future home for commercial-owned pricing and review artifacts after compatibility work is complete
- `configs/`
  - future home for commercial-owned static pricing and approval configuration once it can be separated safely

## Out of Scope

This boundary does not yet absorb:

- acquisition discovery logic
- upstream document parsing ownership
- submission execution logic
- frontend assets
