# Router Failure Matrix

Audit date: 2026-07-16
Pre-patch source import: Python 3.9 `.venv`, `app.main`

Note: the same `/app` path-context failure appeared as `[Errno 1] Operation not permitted: '/app'` in the sandboxed pre-patch import and as `[Errno 30] Read-only file system: '/app'` in the escalated after-patch parity run. Both point to import-time absolute `/app` access outside the running container path context.

| Router | Module | Classification | Error evidence | Running OpenAPI presence | Minimal safe repair |
| --- | --- | --- | --- | --- | --- |
| `smart_harvester_v31_router` | `app.api.smart_harvester_v31_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison; acquisition routes are present in running runtime family but exact route names differ by path. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `real_rfq_harvester_v32_router` | `app.api.real_rfq_harvester_v32_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `real_portal_rfq_extraction_v33_router` | `app.api.real_portal_rfq_extraction_v33_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `structured_rfq_extractor_v34_router` | `app.api.structured_rfq_extractor_v34_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `playwright_live_dom_extractor_v35_router` | `app.api.playwright_live_dom_extractor_v35_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `interactive_playwright_extractor_v36_router` | `app.api.interactive_playwright_extractor_v36_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `deep_rfq_link_extractor_v37_router` | `app.api.deep_rfq_link_extractor_v37_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `interactive_click_deep_extraction_v38_router` | `app.api.interactive_click_deep_extraction_v38_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `true_navigation_extraction_v39_router` | `app.api.true_navigation_extraction_v39_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `tender_form_intelligence_router` | `app.api.tender_form_intelligence_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `csd_persistent_session_router` | `app.api.csd_persistent_session_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `csd_monthly_refresh_router` | `app.api.csd_monthly_refresh_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `final_automation_router` | `app.api.final_automation_layer_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `sbd_intelligence_router` | `app.api.sbd_intelligence_api` | ROUTER_REGISTRY_MISMATCH | `/app` path write/access failure | Requires OpenAPI route comparison. | Remove import-time hard-coded `/app` access or validate under the container `/app` path context. |
| `rfq_lifecycle_router` | `app.api.rfq_lifecycle_api` | PYTHON39_ANNOTATION | FastAPI/Pydantic could not evaluate `dict | None` under Python 3.9 without `eval_type_backport`. | Running runtime uses Python 3.12 and can evaluate this annotation. | Replace the endpoint annotation with `Optional[Dict[str, Any]]`. Applied. |

## Current Interpretation

The RFQ lifecycle failure is a source compatibility bug under the host Python 3.9 environment. The other failures are source/runtime environment mismatches caused by import-time `/app` access outside the container context; they should not be hidden by broad exception suppression or by declaring mandatory routers optional.
