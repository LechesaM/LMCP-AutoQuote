# Phase 2 Extraction Index

Date: 2026-06-22
Scope: baseline index for controlled Phase 2 service extraction

## 1. Modules Successfully Extracted by Service

### Governance

- `app/monitoring/health_service.py` -> `lmcp-core/services/governance/health_service.py`
- `app/monitoring/runtime_diagnostics.py` -> `lmcp-core/services/governance/runtime_diagnostics.py`
- `app/monitoring/metrics_service.py` -> `lmcp-core/services/governance/metrics_service.py`

### Acquisition

- `app/services/harvest_source_registry_service.py` -> `lmcp-core/services/acquisition/harvest_source_registry_service.py`
- `app/services/portal_crawl_priority.py` -> `lmcp-core/services/acquisition/portal_crawl_priority.py`

### Intelligence

- `app/services/rfq_normalizer.py` -> `lmcp-core/services/intelligence/rfq_normalizer.py`
- `app/services/amount_quantity_integrity_validation_engine.py` -> `lmcp-core/services/intelligence/amount_quantity_integrity_validation_engine.py`

### Commercial

- `app/services/profitability.py` -> `lmcp-core/services/commercial/profitability.py`
- `app/services/quote_pricing_engine_service.py` -> `lmcp-core/services/commercial/quote_pricing_engine_service.py`

### Submission

- None. No safe isolated submission utility was extracted.

## 2. Compatibility Shims Created

Original import paths were preserved through compatibility wrappers at the source locations:

- `app/monitoring/health_service.py`
- `app/monitoring/runtime_diagnostics.py`
- `app/monitoring/metrics_service.py`
- `app/services/harvest_source_registry_service.py`
- `app/services/portal_crawl_priority.py`
- `app/services/rfq_normalizer.py`
- `app/services/amount_quantity_integrity_validation_engine.py`
- `app/services/profitability.py`
- `app/services/quote_pricing_engine_service.py`

These shims continue to satisfy existing imports without changing API routes or runtime behavior.

## 3. Modules Intentionally Not Moved

### Governance

- `reporting_service`
- `audit_trail_service`
- `system_state_service`
- any lock/control modules with broader coupling

### Acquisition

- Playwright/browser automation modules
- Celery task orchestration
- tender pipeline modules

### Intelligence

- OCR engines
- PDF extraction pipelines
- Playwright-assisted extraction modules
- Celery tasks

### Commercial

- adjudication engines
- pricing pipelines
- RFQ lifecycle orchestration
- review queues
- final submission compilers

### Submission

- browser automation execution
- portal upload workflows
- Celery orchestration
- final submission compilers
- schedulers
- go-live guards
- any module that can trigger an irreversible operation

## 4. Current Verification Commands

Use the project virtual environment for runtime checks:

```bash
/Users/cash/Documents/.venv/bin/python -m py_compile /Users/cash/Documents/app/main.py
/Users/cash/Documents/.venv/bin/pytest /Users/cash/Documents/tests/test_main_health_status_routes.py
/Users/cash/Documents/.venv/bin/pytest /Users/cash/Documents/tests/test_main_runtime_surface.py
/Users/cash/Documents/.venv/bin/python - <<'PY'
from app.main import health, status
print(bool(health()))
print(bool(status()))
PY
```

## 5. Environment Note

Use the project `.venv` for verification and imports, not the system `python3`.

The system interpreter in this workspace may not have all runtime dependencies available, which can produce false negatives such as missing `sqlalchemy`.

## 6. Remaining High-Risk Areas

- acquisition browser automation and tender orchestration
- intelligence OCR/PDF/Playwright extraction pipelines
- commercial pricing, adjudication, and RFQ lifecycle ownership
- submission browser execution, portal upload, and proof generation
- any Celery task that owns workflow state rather than a pure helper
- any module that mutates runtime JSON, lock files, or immutable audit records during active workflow execution

## 7. Recommended Next Phase

1. Add focused tests around the already extracted helper modules.
2. Expand compatibility coverage for the shims if needed.
3. Only then consider acquisition orchestration extraction, and keep browser automation and Celery task ownership deferred until the helper layer is stable.

## 8. Definition of Done for Phase 2 Baseline

Phase 2 baseline is complete when:

- low-risk helper modules are relocated into the appropriate `lmcp-core/services/*` landing zones
- original import paths continue to work through shims
- backend `/health` and `/status` remain available
- the existing runtime tests still pass under the project `.venv`
- no browser automation, portal upload, pricing workflow, adjudication workflow, or submission workflow has been destabilized
- all remaining high-risk workflow modules are clearly documented and intentionally left in place

