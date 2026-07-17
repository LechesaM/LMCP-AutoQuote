# Phase 31/32 Minimal Recovery Plan

## Decision

Do not copy or cherry-pick the whole `origin/release/v1.1` operator workflow stack. It is verified historical evidence, but it is not a safe direct restore because it depends on older or absent modules and release-branch `live_rfq_store.py` functions that would conflict with the current recovered store and newer enterprise services.

No patch was applied during this audit.

## Minimal Recovery Set

### 1. Add a Read-Only Canonical Work-Item Adapter

- Target: new additive backend route, either:
  - `app/api/rfq_work_items_api.py` with `/rfq-work-items` and `/rfq-work-items/{rfq_id}`, or
  - compatibility route `/operations/rfqs` and `/operations/rfqs/{rfq_id}`.
- Evidence source:
  - `origin/release/v1.1:app/api/operator_workflow_routes.py`
  - `origin/release/v1.1:app/api/operator_workflow_contracts.py`
  - current `app/api/rfq_lifecycle_api.py`
  - current `app/services/rfq_lifecycle_service.py`
  - current `app/api/rfq_stable_api.py`
  - current `app/api/quotes_stable_api.py`
  - current `frontend/src/components/RfqOperationsWorkspace.jsx`
- Method: adapt, not copy. Use release route names and response-shape ideas, but source fields from current services.
- Initial scope: GET only.
- Fields to expose:
  - canonical id/reference/title/buyer/closing date/source URL
  - lifecycle state and readiness label
  - documents, BOQs, pricing schedules, returnables, proofs
  - quote pack and submission pack paths/statuses
  - manual pricing status/paths/line item count if present
  - blockers/readiness reasons
- Dependencies:
  - current RFQ lifecycle state store
  - current stable RFQ/quote readers
  - current quote-compilation candidates where safe
- Regression risk: medium if additive; high if it replaces current routers.

### 2. Preserve Current Enterprise Modules

These files must not be replaced by historical versions:

- `app/services/live_rfq_store.py`
- `app/services/rfq_lifecycle_service.py`
- `app/services/rfq_state_store.py`
- `app/services/rfq_document_acquisition_engine.py`
- `app/services/rfq_document_intelligence.py`
- `app/services/rfq_boq_extraction_engine.py`
- `app/services/quote_compilation_service.py`
- `app/api/quote_compilation_api.py`
- `app/services/final_submission_v47_5_service.py`
- `app/services/tender_harvester.py`
- `frontend/src/components/RfqOperationsWorkspace.jsx`

Historical files can be referenced for contract evidence, but not used as direct replacements.

### 3. Defer Mutating Workflow/Submission Execution

Do not restore or execute the historical mutating submission execution path until the read-only work-item route is proven.

Historical files requiring extra review:

- `origin/release/v1.1:app/services/submission_execution_service.py`
- `origin/release/v1.1:app/services/submission_package_service.py`
- `origin/release/v1.1:app/services/submission_quality_service.py`
- `origin/release/v1.1:app/services/governed_submission_service.py`
- `origin/release/v1.1:app/services/submission_receipt_verification_service.py`
- `origin/release/v1.1:app/services/physical_submission_governance_service.py`

Several of these write runtime records when called. They are not appropriate for blind restoration during a read-only recovery pass.

### 4. Restore Frontend Binding Only After Backend Adapter Exists

- Current frontend already renders documents, BOQs, pricing schedules, readiness, manual pricing, quote pack, and proof artifacts if the backend supplies them.
- Do not modify frontend during this task.
- Later frontend change should be limited to adding the verified work-item endpoint to `RFQ_ENDPOINTS` or replacing the historical endpoint list with the new adapter.

### 5. Fix Live RFQ Data Alignment Separately

The Live RFQ Store audit classified the current break as `ACQUISITION_WRITES_ELSEWHERE`. That is a separate repair from Phase 31/32 work-item recovery.

Do not clear or repopulate `runtime/live_rfqs.json`. The narrow repair is to bridge the active acquisition output into `promote_live_rfqs` after reviewing current acquisition output shape.

## Proposed First Patch

No patch is proposed for immediate application in this audit because the first missing capability has high conceptual confidence but medium implementation risk:

- Direct historical copy is unsafe.
- The correct repair is an adapted route built against current services.
- That route should be reviewed as a separate, explicit implementation task.

## Tests and Validation For Future Patch

Run after adding the read-only adapter:

```bash
.venv/bin/python -m py_compile app/api/rfq_work_items_api.py
.venv/bin/python -m py_compile app/main.py
.venv/bin/python -m pytest tests/test_rfq_lifecycle_validate_visible_opportunities.py tests/test_rfq_lifecycle_upload_dry_run_status.py
cd frontend && npm run build
```

Also compare OpenAPI paths before and after:

```bash
curl -s http://localhost:8000/openapi.json > /tmp/openapi-before.json
curl -s http://localhost:8000/openapi.json > /tmp/openapi-after.json
```

The adapter must add routes without removing existing paths.

## Rollback Procedure

If the future adapter patch fails:

1. Remove only the new adapter route file.
2. Remove only the new router registration line.
3. Re-run `py_compile` and OpenAPI comparison.
4. Do not revert unrelated user or recovery files.

## Files That Must Remain Untouched

- All runtime data under `runtime/`
- Docker volumes
- PostgreSQL data
- Redis data
- harvested documents
- submission proofs
- quote packs
- current enterprise service implementations listed above

## Narrowest Next Action

Prepare a small read-only backend adapter PR that exposes canonical RFQ work-items from current lifecycle/stable/live data, using `origin/release/v1.1` only as a response-contract reference.
