# SBD Route Ownership Matrix

Audit date: 2026-07-16
Branch: recovery/rfq-quote-pack-bridge
Commit: c02c0d56

## Decision

Canonical owner for `/sbd-intelligence/status` and `/sbd-intelligence/complete` is `app.api.sbd_intelligence_api`.

The duplicate owner was `app.api.tender_form_intelligence_api`, which was a tender-form compatibility facade accidentally mounted at the SBD public prefix. It now owns `/tender-form-intelligence/*`, matching the running OpenAPI and status links in `app/main.py`.

## Ownership Evidence

| Method/path | Canonical owner | Duplicate/facade owner | Running OpenAPI operation ID | Source operation ID after repair | Decision |
| --- | --- | --- | --- | --- | --- |
| `GET /sbd-intelligence/status` | `app.api.sbd_intelligence_api:sbd_intelligence_status` | formerly `app.api.tender_form_intelligence_api:status` | `sbd_intelligence_status_sbd_intelligence_status_get` | `sbd_intelligence_status_sbd_intelligence_status_get` | Keep SBD API as canonical owner. |
| `POST /sbd-intelligence/complete` | `app.api.sbd_intelligence_api:sbd_intelligence_complete` | formerly `app.api.tender_form_intelligence_api:complete` | `sbd_intelligence_complete_sbd_intelligence_complete_post` | `sbd_intelligence_complete_sbd_intelligence_complete_post` | Keep SBD API as canonical owner. |

## Implementation Comparison

| Attribute | `app.api.sbd_intelligence_api` | `app.api.tender_form_intelligence_api` |
| --- | --- | --- |
| Current public prefix | `/sbd-intelligence` | `/tender-form-intelligence` |
| Role | Canonical SBD compatibility API. | Tender-form intelligence facade. |
| Request contract | `POST /complete` requires JSON body via `Body(...)`; status takes no body. | `POST` routes accept JSON dict payload. |
| Response contract | Dict response from `tender_form_intelligence_engine` with fallback error/status envelopes. | Dict response from direct tender-form intelligence functions. |
| Service dependency | `app.services.tender_form_intelligence_engine` imported as `engine`. | Direct imports from `app.services.tender_form_intelligence_engine`. |
| Runtime side effects | Import-safe after runtime-path repair; operation may create tender-form output during explicit completion. | Import-safe after runtime-path repair; operation may create tender-form output during explicit completion. |
| Safety controls | No autonomous submission; form completion is explicit POST only. | No autonomous submission; form completion is explicit POST only. |
| Registration path | `app/main.py` optional router `sbd_intelligence_router`. | `app/main.py` optional router `tender_form_intelligence_router`. |
| Historical evidence | Present in `v2.0-operational-baseline`, `recovery-2026-07-15`, `origin/release/v1.1`; running OpenAPI operation IDs match this module. | Historical backups and `app/main.py` status links point to `/tender-form-intelligence/*`; current baseline had this facade incorrectly using `/sbd-intelligence`. |
| Classification | Newer/canonical SBD compatibility route. | Facade/compatibility route for tender-form operations. |

## Fix Applied

Changed only the facade prefix:

```python
router = APIRouter(prefix="/tender-form-intelligence", tags=["Tender Form Intelligence"])
```

No SBD public path, method, operation function name, or service logic was changed. No route family was removed.

## Validation

Focused test: `tests/test_sbd_route_ownership.py`

Assertions:

- exactly one `GET /sbd-intelligence/status`;
- exactly one `POST /sbd-intelligence/complete`;
- exactly one `GET /tender-form-intelligence/status`;
- exactly one `POST /tender-form-intelligence/complete`;
- zero duplicate method/path pairs;
- canonical SBD operation IDs remain stable.

Result: passed.
