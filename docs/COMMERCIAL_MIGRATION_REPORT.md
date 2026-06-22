# Commercial Migration Report

Date: 2026-06-22
Scope: first controlled commercial extraction into `lmcp-core/services/commercial/`

## Objective

Create the initial `lmcp-core` commercial landing zone without breaking:

- `app.main:app`
- `/health`
- `/status`
- current pricing queue behavior
- current pricing and review runtime paths
- existing imports and API routes

## Commercial Source Assets

The current commercial surface includes:

- pricing engines and real-profit enrichment
- supplier matching and supplier comparison
- adjudication and supplier award logic
- quote normalization, compilation, and quote-pack generation
- manual pricing workflows and commercial review gates
- RFQ lifecycle commercial state transitions

Primary live source modules:

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

## Pricing and Adjudication Entrypoints

Active task and lifecycle entrypoints:

- `app.tasks.rfq_lifecycle_pricing_task`
- `app.services.rfq_lifecycle_service.RfqLifecycleService.advance_parsed`
- manual pricing save/validation flows inside `app.services.rfq_lifecycle_service`

Active API entrypoints:

- `app/api/quote_engine_api.py`
- `app/api/quote_compilation_api.py`
- `app/api/quote_pack_api.py`
- `app/api/quote_pack_v44_api.py`
- `app/api/real_profit_pricing_api.py`
- `app/api/auto_pricing_v43_api.py`
- `app/api/supplier_quotes_api.py`
- `app/api/tender_pipeline_api.py`

## Celery Ownership

Current queue ownership is shared with the lifecycle runtime:

- `pricing_queue`
  - exposed by `app.tasks.rfq_lifecycle_pricing_task`
  - actual pricing progression runs inside `RfqLifecycleService.advance_parsed`
- `retry_queue`
  - receives `REVIEW_REQUIRED` and other blocked commercial cases through lifecycle orchestration
- `proof_queue`
  - receives `QUOTE_PACK_READY` handoff, which makes commercial completion depend on downstream submission flow

Commercial is therefore not yet an isolated worker boundary. Queue ownership is logical, but execution still flows through the monolithic lifecycle service.

## Database Ownership Targets

Canonical target ownership for Commercial Service should include:

- quote drafts
- quote line items
- quote packs
- quote pack items
- quote pack status history
- quote pack edit audit records
- supplier comparison and award decision records

Current actual ownership is still split across:

- `quote_drafts`, `quote_line_items`, and `supplier_items` in `app/models/core.py`
- `quote_packs`, `quote_pack_items`, `quote_pack_status_history`, and `quote_pack_edit_audit` in `app/quote_pack_models.py`
- filesystem-backed JSON artifacts in `runtime/*`

## Filesystem and Runtime Dependencies

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

## Pricing State Ownership

Pricing state is currently split across:

- RFQ lifecycle item fields such as `pricing_result`, `pricing_review_status`, `pricing_verification_status`, `manual_pricing_required`, and `quote_pack_path`
- manual pricing JSON under runtime-controlled paths
- quote-pack relational tables
- pricing output artifacts under `runtime/pricing_engine/` and `runtime/real_profit_pricing/`

This is not yet a single canonical commercial state model.

## Approval and Review Workflow Ownership

Approval and review ownership is also split:

- quote-review workflow state lives in `quote_packs` relational tables
- manual approval logging writes to `manual_production/approvals.jsonl`
- review queue exports and backups write into `runtime/manual_review/`
- lifecycle transitions still determine whether an RFQ becomes `REVIEW_REQUIRED`, `PRICED`, `PRICING_VERIFIED`, or `QUOTE_PACK_READY`

Commercial review is therefore shared between relational persistence, runtime files, and lifecycle state.

## Coupling Risks

The main coupling risks that still block direct source relocation are:

- pricing and quote-pack generation are orchestrated inside `rfq_lifecycle_service`
- `tender_pipeline.py` bridges pricing, supplier, and downstream submission concerns
- manual pricing validation and persistence are embedded in lifecycle state management
- review and approval services depend on both runtime folders and relational tables
- commercial readiness is partially derived from intelligence outputs and partially from manually edited pricing state

## Unsafe Shared State

The current unsafe shared-state patterns include:

- runtime JSON and folder artifacts used as operational commercial state
- review queue and manual pricing files acting as mutable workflow state
- duplicate persistence across SQLAlchemy tables, JSON artifacts, and lifecycle item fields
- quote-pack outputs shared between commercial completion and downstream submission preparation

## Hidden Workflow Dependencies

The major hidden workflow dependencies are:

- `RfqLifecycleService.advance_parsed` performs commercial gating, pricing, and quote-pack generation in one step
- quote-pack readiness automatically determines handoff to `proof_queue`
- manual pricing verification changes lifecycle state directly
- review-required outcomes route into retry workflows rather than a purely commercial queue
- supplier award and submission-pack helpers overlap with submission-facing artifacts even though submission extraction has not happened yet

## Future Extraction Order

Recommended commercial extraction order:

1. Extract commercial-owned documentation and static config contracts first.
2. Extract read-only pricing policy and margin helpers behind compatibility wrappers.
3. Extract runtime path adapters for pricing outputs, quote packs, and review artifacts.
4. Extract quote-pack persistence and review services after canonical state ownership is clarified.
5. Extract lifecycle-facing pricing orchestration and API routers last, after queue and persistence ownership are isolated.

Modules that should wait:

- `app/services/tender_pipeline.py`
- `app/services/quote_review_service.py`
- `app/services/real_profit_pricing_service.py`
- `app/services/quote_pack_service.py`
- `app/services/supplier_award_execution_service.py`
- `app/services/rfq_lifecycle_service.py`

## What Was Migrated

The migration was intentionally limited to commercial-owned documentation and target scaffolding:

- updated `lmcp-core/services/commercial/README.md`
- created `lmcp-core/services/commercial/docs/SOURCE_MAP.md`
- created `lmcp-core/services/commercial/runtime/README.md`
- created `lmcp-core/services/commercial/configs/README.md`

This establishes the `lmcp-core` target boundary for commercial without changing runtime behavior.

## Rollback Instructions

This migration is documentation-only and can be rolled back without runtime impact by removing:

- `lmcp-core/services/commercial/docs/SOURCE_MAP.md`
- `lmcp-core/services/commercial/runtime/README.md`
- `lmcp-core/services/commercial/configs/README.md`
- the updated content in `lmcp-core/services/commercial/README.md`
- `docs/COMMERCIAL_MIGRATION_REPORT.md`

No backend imports, API routes, task registration, runtime files, or compose files were changed in this step.
