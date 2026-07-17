# RFQ Lifecycle Manual Pricing Route Matrix

Audit date: 2026-07-16
Branch: `recovery/rfq-quote-pack-bridge`
Evidence sources:

- `docs/recovery/running_only_route_disposition.md`
- `docs/recovery/runtime_route_difference_matrix.json`
- `origin/release/v1.1:app/api/rfq_lifecycle_api.py`
- `origin/release/v1.1:app/services/rfq_lifecycle_service.py`
- `app/api/rfq_lifecycle_api.py`
- `app/services/rfq_lifecycle_service.py`

## Summary

The four highest-priority RFQ lifecycle/manual-pricing running-only routes were genuine compatibility gaps in current source. Their historical route decorators existed in `origin/release/v1.1:app/api/rfq_lifecycle_api.py`, while current source retained the broader RFQ lifecycle service and route stack but did not expose these method/path pairs.

Current source now restores the public method/path and historical operation IDs through `app.api.rfq_lifecycle_api`, delegating to current `RfqLifecycleService` methods. The restoration is intentionally narrower than the historical implementation where required for recovery safety:

- manual-pricing persistence is local lifecycle/manual-pricing persistence only and does not upsert the Live RFQ Store;
- visible-opportunity validation is dry-run/read-only by default and does not execute external acquisition or lifecycle/live-store writes;
- autonomous submission remains disabled.

## Route Matrix

| Method | Path | Running operation ID | Historical source | Current equivalent | Decision | Safety behavior |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/rfq-lifecycle/manual-pricing/{rfq_id}` | `manual_pricing_rfq_lifecycle_manual_pricing__rfq_id__get` | `origin/release/v1.1:app/api/rfq_lifecycle_api.py` -> `RfqLifecycleService.get_manual_pricing` | Restored in `app/api/rfq_lifecycle_api.py`; delegates to current `RfqLifecycleService.get_manual_pricing` | `RESTORE_COMPATIBILITY_ROUTE` | Read-only lookup from lifecycle/manual-pricing state and Live RFQ index. |
| `POST` | `/rfq-lifecycle/manual-pricing/{rfq_id}` | `save_manual_pricing_rfq_lifecycle_manual_pricing__rfq_id__post` | `origin/release/v1.1:app/api/rfq_lifecycle_api.py` -> `RfqLifecycleService.save_manual_pricing` | Restored in `app/api/rfq_lifecycle_api.py`; delegates to current `RfqLifecycleService.save_manual_pricing` | `RESTORE_COMPATIBILITY_ROUTE` | Operator-triggered local pricing save. Does not upsert `runtime/live_rfqs.json`; tests use temp stores. |
| `POST` | `/rfq-lifecycle/reject-terminal-review-items` | `reject_terminal_review_items_rfq_lifecycle_reject_terminal_review_items_post` | `origin/release/v1.1:app/api/rfq_lifecycle_api.py` -> `RfqLifecycleService.reject_terminal_review_items` | Restored in `app/api/rfq_lifecycle_api.py`; delegates to current `RfqLifecycleService.reject_terminal_review_items` | `RESTORE_COMPATIBILITY_ROUTE` | Mutates lifecycle state only when explicitly invoked; rejects only terminal review blockers. No import-time writes. |
| `POST` | `/rfq-lifecycle/validate-visible-opportunities` | `validate_visible_opportunities_rfq_lifecycle_validate_visible_opportunities_post` | `origin/release/v1.1:app/api/rfq_lifecycle_api.py` -> `RfqLifecycleService.validate_visible_opportunities` | Restored in `app/api/rfq_lifecycle_api.py`; delegates to current safe compatibility method | `RESTORE_COMPATIBILITY_ROUTE` | Dry-run/read-only by default; no external validation, no Live RFQ Store writes, no lifecycle writes, no local pack generation unless explicitly requested by operator code. |

## Current Equivalence Assessment

`GET /manual-pricing/{rfq_id}` is equivalent for route compatibility and response intent: it returns saved manual pricing state when available and reports `not_found` when no RFQ can be resolved.

`POST /manual-pricing/{rfq_id}` is intentionally safer than the historical source. Historical evidence also updated lifecycle state and Live RFQ Store records. The recovered source keeps lifecycle/manual-pricing persistence but avoids Live RFQ Store upsert to respect recovery constraints.

`POST /reject-terminal-review-items` is restored through current lifecycle primitives and applies only terminal blocker codes such as `not_supply_and_delivery`, `closing_date_passed`, and `missing_closing_date`.

`POST /validate-visible-opportunities` is restored as a compatibility/dry-run route. Historical behavior could validate and promote visible records. Current recovery behavior reports what would be promoted or blocked without starting acquisition, external validation, local pack generation, or store mutation by default.

## Validation Evidence

- `tests/test_rfq_lifecycle_manual_pricing_compatibility.py` verifies route uniqueness, operation IDs, service delegation, temporary-store manual pricing behavior, dry-run visible validation behavior, and autonomous-disabled defaults.
- Post-change route comparison classifies all four routes as `PRESENT_IN_BOTH` with matching operation IDs.
- Protected runtime store hashes remained unchanged.
