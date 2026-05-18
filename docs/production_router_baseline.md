# Production Router Baseline

This document defines the frozen Branch A routing baseline for LMCP AutoQuote.

## Active production routers

The default startup path loads only `PRODUCTION_ROUTER_SPECS` through `iter_router_specs()`:

- `supplier_quotes_router`
- `email_ingestion_router`
- `csd_router`
- `opportunities_router`
- `submission_history_recent_router`
- `submission_history_pipeline_sync_router`
- `proof_of_submission_router`
- `submission_history_proof_enrichment_router`
- `quotes_stable_router`
- `rfq_stable_router`
- `system_stable_router`
- `audit_api`
- `compliance_api`
- `harvester_api`
- `sbd_api`
- `system_guard_api`
- `quote_compilation_router`
- `dashboard`
- `form_filler_api`
- `sbd_version_detector_api`
- `supply_command_api`
- `submission_history_router`
- `submission_analytics_router`
- `decision_intelligence_router`
- `operator_actions_router`
- `operator_auth_router`
- `audit_trail_router`
- `go_live_guard_router`
- `pipeline_enforcement_router`
- `security_router`
- `portal_submission_router`
- `proof_center_router`
- `sbd_completion_router`
- `etenders_session_router`
- `handwriting_form_overlay_router`
- `handwriting_glyph_router`
- `handwriting_field_detector_router`
- `tender_form_intelligence_router`
- `csd_persistent_session_router`
- `csd_monthly_refresh_router`
- `sbd_intelligence_router`
- `production_lock_router`
- `real_profit_pricing_router`
- `rfq_lifecycle_router`
- `mission_control_compat_router`

## Legacy router policy

- `LEGACY_ROUTER_SPECS` contains versioned routers and overlapping non-versioned routers that are no longer part of the trusted manual-production path.
- Legacy routers do not load by default.
- Legacy routers load only when `LMCP_ENABLE_LEGACY_ROUTERS` is truthy.
- Duplicate active routes remain a startup failure. `main.py` must continue loading routers through `iter_router_specs()`.

## Freeze rules

- No new versioned routers may be added without deprecating or replacing the old route in the registry.
- Do not create parallel execution systems for manual production, portal submission, or final submission.
- The manual production path must remain human-approved.
- Final submission stays manual-only unless explicitly unlocked later.
- Keep the existing business rules unchanged:
  - supply and delivery only
  - exclude medical consumables, IT equipment, petrol, diesel, catering, compulsory briefing sessions
  - minimum profit `R30,000`
  - minimum supply margin `25%`
