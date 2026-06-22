# LMCP Database Source of Truth

## Purpose
This document defines how LMCP should treat PostgreSQL as the canonical source of truth for runtime state without changing production tables yet.

The current codebase has three active persistence classes:

1. PostgreSQL/SQLAlchemy-backed application models via [app/db/session.py](/Users/cash/Documents/app/db/session.py), [app/db/base.py](/Users/cash/Documents/app/db/base.py), and models under [app/models](/Users/cash/Documents/app/models), [app/quote_pack_models.py](/Users/cash/Documents/app/quote_pack_models.py), [app/compliance_models.py](/Users/cash/Documents/app/compliance_models.py), and [app/sbd_models.py](/Users/cash/Documents/app/sbd_models.py).
2. Runtime JSON stores under [runtime](/Users/cash/Documents/runtime), especially [app/services/rfq_state_store.py](/Users/cash/Documents/app/services/rfq_state_store.py), [app/services/live_rfq_store.py](/Users/cash/Documents/app/services/live_rfq_store.py), [app/services/system_state_service.py](/Users/cash/Documents/app/services/system_state_service.py), and submission history writers in [app/services/tender_pipeline.py](/Users/cash/Documents/app/services/tender_pipeline.py).
3. Secondary SQLite stores, notably [app/persistence/db.py](/Users/cash/Documents/app/persistence/db.py), [runtime/manual_production/lmcp_operations.db](/Users/cash/Documents/runtime/manual_production/lmcp_operations.db), [runtime/operator_auth/operator_auth.sqlite3](/Users/cash/Documents/runtime/operator_auth/operator_auth.sqlite3), [runtime/harvest.db](/Users/cash/Documents/runtime/harvest.db), and [etenders_acquisition/workflow_layer/workflow_db.py](/Users/cash/Documents/etenders_acquisition/workflow_layer/workflow_db.py).

In official production, [docker-compose.production.yml](/Users/cash/Documents/docker-compose.production.yml) already points the backend and workers at PostgreSQL. The problem is that important operational state still bypasses PostgreSQL and is written to JSON or SQLite.

## Current Persistence Surface

### SQLAlchemy/PostgreSQL-capable models
These models already fit the intended canonical store:

- `opportunities`, `quote_drafts`, `quote_line_items`, `submission_records`, `supplier_items`, `audit_logs` in [app/models/core.py](/Users/cash/Documents/app/models/core.py)
- `buyer_events`, `buyer_profiles`, `procurement_signals`, `supplier_products` in [app/models](/Users/cash/Documents/app/models)
- `quote_packs`, `quote_pack_items`, `quote_pack_status_history`, `quote_pack_edit_audit` in [app/quote_pack_models.py](/Users/cash/Documents/app/quote_pack_models.py)
- compliance and SBD tables in [app/compliance_models.py](/Users/cash/Documents/app/compliance_models.py) and [app/sbd_models.py](/Users/cash/Documents/app/sbd_models.py)

### File-backed runtime state
These currently behave like mutable system-of-record stores even though they are files:

- RFQ lifecycle: [runtime/rfq_lifecycle/rfqs.json](/Users/cash/Documents/runtime/rfq_lifecycle/rfqs.json)
- RFQ lifecycle audit: [runtime/rfq_lifecycle/audit_events.json](/Users/cash/Documents/runtime/rfq_lifecycle/audit_events.json)
- RFQ lifecycle telemetry: [runtime/rfq_lifecycle/telemetry.json](/Users/cash/Documents/runtime/rfq_lifecycle/telemetry.json)
- live RFQ index: [runtime/live_rfqs.json](/Users/cash/Documents/runtime/live_rfqs.json)
- system control state: [runtime/system_state/system_state.json](/Users/cash/Documents/runtime/system_state/system_state.json)
- submission history: [runtime/submission_history/submission_history.json](/Users/cash/Documents/runtime/submission_history/submission_history.json)
- portal/final submission histories under [runtime/final_submission_v47_5](/Users/cash/Documents/runtime/final_submission_v47_5) and [runtime/submission_history](/Users/cash/Documents/runtime/submission_history)
- auth users: [runtime/auth/users.json](/Users/cash/Documents/runtime/auth/users.json)
- cycle state: `data/crawl_cycle_state.json` via [app/services/cycle_state_store.py](/Users/cash/Documents/app/services/cycle_state_store.py)

### Secondary SQLite stores
These create split-brain risk because they store operational state outside PostgreSQL:

- manual production workflow/event/audit tables in [app/persistence/db.py](/Users/cash/Documents/app/persistence/db.py)
- operator auth SQLite path configured in [app/config.py](/Users/cash/Documents/app/config.py)
- workflow layer SQLite in [etenders_acquisition/workflow_layer/workflow_db.py](/Users/cash/Documents/etenders_acquisition/workflow_layer/workflow_db.py)
- acquisition-side SQLite models in [etenders_acquisition/app/db/models.py](/Users/cash/Documents/etenders_acquisition/app/db/models.py)

### Celery persistence
Celery is configured in [app/celery_app.py](/Users/cash/Documents/app/celery_app.py):

- broker: Redis
- result backend: Redis
- beat schedule: runtime/local SQLite files such as [runtime/celerybeat-schedule.db](/Users/cash/Documents/runtime/celerybeat-schedule.db)

Redis/Celery currently provides transport and transient execution result storage, not the authoritative domain record. Task state visible through `AsyncResult` or the result backend must not be treated as canonical business state.

## Canonical Entities
The following entities should be canonical database state in PostgreSQL.

### 1. Tenders
Canonical meaning: one buyer opportunity discovered by acquisition and tracked through submission outcome.

Current sources:

- `opportunities` in [app/models/core.py](/Users/cash/Documents/app/models/core.py)
- `tenders` in [etenders_acquisition/app/db/models.py](/Users/cash/Documents/etenders_acquisition/app/db/models.py)
- RFQ records in [runtime/rfq_lifecycle/rfqs.json](/Users/cash/Documents/runtime/rfq_lifecycle/rfqs.json)
- flattened dashboard view in [runtime/live_rfqs.json](/Users/cash/Documents/runtime/live_rfqs.json)

Recommendation:

- PostgreSQL must own the canonical tender row.
- `live_rfqs.json` may remain a derived cache or snapshot only.
- `rfqs.json` should stop being the mutable master once PostgreSQL lifecycle tables exist.

### 2. Documents
Canonical meaning: every source document, generated document, proof artifact, and compliance attachment attached to a tender.

Current sources:

- `tender_documents` in [etenders_acquisition/app/db/models.py](/Users/cash/Documents/etenders_acquisition/app/db/models.py)
- compliance tables in [app/compliance_models.py](/Users/cash/Documents/app/compliance_models.py)
- SBD generated file metadata in [app/sbd_models.py](/Users/cash/Documents/app/sbd_models.py)
- folder presence checks in [runtime/downloaded_tender_documents](/Users/cash/Documents/runtime/downloaded_tender_documents) and multiple runtime pack folders

Recommendation:

- PostgreSQL must own document metadata, classification, checksum, source URL, owning tender, and processing status.
- Files themselves remain file-based.
- Folder existence alone must not define document state.

### 3. BOQ extraction
Canonical meaning: extraction job, extracted rows, confidence, and verification outcome for a document.

Current sources:

- `boq_extractions` and `boq_items` in [etenders_acquisition/app/db/models.py](/Users/cash/Documents/etenders_acquisition/app/db/models.py)
- JSON outputs under [runtime/boq_intelligence](/Users/cash/Documents/runtime/boq_intelligence)

Recommendation:

- PostgreSQL must own extraction attempts, current status, source document link, and normalized row set.
- BOQ JSON files may remain exports/debug artifacts, not master state.

### 4. Pricing
Canonical meaning: pricing run, assumptions, selected supplier set, totals, margin, validation outcomes, and final approved commercial position.

Current sources:

- `quote_drafts` and `quote_line_items` in [app/models/core.py](/Users/cash/Documents/app/models/core.py)
- `quote_packs` and `quote_pack_items` in [app/quote_pack_models.py](/Users/cash/Documents/app/quote_pack_models.py)
- JSON outputs under [runtime/pricing_engine](/Users/cash/Documents/runtime/pricing_engine), [runtime/real_profit_pricing](/Users/cash/Documents/runtime/real_profit_pricing), [runtime/pricing_summaries](/Users/cash/Documents/runtime/pricing_summaries)

Recommendation:

- PostgreSQL must own the active pricing record and approval-relevant commercial values.
- generated pricing summaries may remain file exports.

### 5. Adjudication
Canonical meaning: supplier comparison, risk findings, award recommendation, and governance decision.

Current sources:

- status history and edit audit in [app/quote_pack_models.py](/Users/cash/Documents/app/quote_pack_models.py)
- JSON outputs under [runtime/supplier_quote_adjudication](/Users/cash/Documents/runtime/supplier_quote_adjudication), [runtime/ai_tender_adjudication](/Users/cash/Documents/runtime/ai_tender_adjudication), and [runtime/live_supplier_responses](/Users/cash/Documents/runtime/live_supplier_responses)

Recommendation:

- PostgreSQL must own the latest adjudication decision and operator-approved decision lineage.
- supporting matrices and full analysis reports may remain immutable evidence files with DB references.

### 6. Submissions
Canonical meaning: readiness, approval, dispatch attempt, portal/email result, proof capture, and final submission outcome.

Current sources:

- `submission_records` in [app/models/core.py](/Users/cash/Documents/app/models/core.py)
- JSON histories under [runtime/submission_history](/Users/cash/Documents/runtime/submission_history), [runtime/final_submission_v47_5](/Users/cash/Documents/runtime/final_submission_v47_5), [runtime/portal_submission](/Users/cash/Documents/runtime/portal_submission)
- immutable lock/evidence files in [runtime/locks/immutable_submission](/Users/cash/Documents/runtime/locks/immutable_submission) and [runtime/proof_center](/Users/cash/Documents/runtime/proof_center)

Recommendation:

- PostgreSQL must own the canonical submission row and attempt history.
- proofs, stamped PDFs, screenshots, and manifests remain file-based immutable evidence with database pointers and hashes.

### 7. Workers
Canonical meaning: logical workflow execution, retries, queue assignment, failure cause, and terminal outcome.

Current sources:

- transient Celery state in Redis
- queue/status enums in [app/orchestration/job_models.py](/Users/cash/Documents/app/orchestration/job_models.py)
- telemetry JSON in [runtime/rfq_lifecycle/telemetry.json](/Users/cash/Documents/runtime/rfq_lifecycle/telemetry.json)
- manual production SQLite queue tables in [app/persistence/db.py](/Users/cash/Documents/app/persistence/db.py)

Recommendation:

- PostgreSQL must own logical worker execution records for domain workflows.
- Redis remains transport and short-lived result cache only.

## Canonical Lifecycle States

### Tenders

- `DISCOVERED`
- `QUALIFIED`
- `DOCUMENT_ACQUISITION_PENDING`
- `DOCUMENT_ACQUISITION_BLOCKED`
- `DOCUMENTS_ACQUIRED`
- `DOCUMENTS_PARSED`
- `PRICED`
- `PRICING_VERIFIED`
- `COMMERCIAL_VERIFICATION_REQUIRED`
- `QUOTE_PACK_READY`
- `APPROVAL_READY`
- `SUBMISSION_READY`
- `SUBMITTED`
- `PROOF_CAPTURED`
- `ARCHIVED`
- `FAILED`
- `REVIEW_REQUIRED`
- `READY_FOR_RETRY`
- `REJECTED`

These align closely with the existing lifecycle list in [app/services/rfq_lifecycle_service.py](/Users/cash/Documents/app/services/rfq_lifecycle_service.py).

### Documents

- `DISCOVERED`
- `QUEUED_FOR_DOWNLOAD`
- `DOWNLOADING`
- `DOWNLOADED`
- `CLASSIFIED`
- `PARSED`
- `FAILED`
- `RETRY_PENDING`
- `QUARANTINED`
- `ARCHIVED`

### BOQ extraction

- `PENDING`
- `CANDIDATE`
- `EXTRACTING`
- `EXTRACTED`
- `NORMALIZED`
- `VERIFIED`
- `REVIEW_REQUIRED`
- `FAILED`
- `RETRY_PENDING`

Existing acquisition-side values already include `candidate`, `not_boq`, and extraction failure variants.

### Pricing

- `PENDING`
- `IN_PROGRESS`
- `PRICED`
- `VALIDATION_REQUIRED`
- `APPROVAL_REQUIRED`
- `APPROVED`
- `REJECTED`
- `FAILED`
- `RETRY_PENDING`

### Adjudication

- `PENDING`
- `ANALYZING`
- `RECOMMENDED`
- `REVIEW_REQUIRED`
- `APPROVED`
- `REJECTED`
- `FAILED`

### Submissions

- `PENDING`
- `READY_MANUAL`
- `READY_AUTOMATED`
- `DISPATCHING`
- `SUBMITTED`
- `PROOF_CAPTURED`
- `CONFIRMED`
- `FAILED`
- `RETRY_PENDING`
- `MANUAL_INTERVENTION_REQUIRED`

### Workers

- `PENDING`
- `RUNNING`
- `COMPLETED`
- `FAILED`
- `RETRY_PENDING`
- `BLOCKED`
- `CANCELLED`
- `DEAD_LETTERED`

`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `RETRY_PENDING`, and `BLOCKED` are already reflected in [app/orchestration/job_models.py](/Users/cash/Documents/app/orchestration/job_models.py).

## Ownership Boundaries

### PostgreSQL must own

- tender master records
- document metadata and processing status
- BOQ extraction jobs and normalized output references
- pricing state and approval-relevant totals
- adjudication decisions and status history
- submission attempts and final outcomes
- worker execution records for business workflows
- operator/governance actions

### File system should remain responsible for

- raw downloaded tender documents
- generated DOCX/PDF quote packs
- screenshots, proofs, browser session artifacts, and exports
- large intermediate debug payloads
- logs and cache-like derivative reports

### Immutable audit record class

- state transitions
- operator edits and approvals
- submission evidence manifests
- external proof captures
- commercial release decisions

These should eventually be append-only DB records with references to immutable files where the payload is large.

## Duplicate State Mechanisms

### Tender/runtime duplication

- `opportunities` table
- `etenders_acquisition` SQLite `tenders`
- `runtime/rfq_lifecycle/rfqs.json`
- `runtime/live_rfqs.json`

### Submission duplication

- `submission_records`
- `runtime/submission_history/submission_history.json`
- `runtime/final_submission_v47_5/final_submission_history.json`
- `runtime/submission_history/v47_portal_submission_history.json`

### Auth duplication

- file-backed users in [app/auth/session_service.py](/Users/cash/Documents/app/auth/session_service.py)
- SQLite operator auth path in [app/config.py](/Users/cash/Documents/app/config.py)

### Queue/workflow duplication

- Celery transient task state in Redis
- queue/job JSON rows in manual production SQLite
- lifecycle telemetry JSON

## Folder-Driven State
These patterns are active and unsafe if treated as authoritative:

- infering acquisition/completeness from document presence in [runtime/downloaded_tender_documents](/Users/cash/Documents/runtime/downloaded_tender_documents)
- inferring quote readiness from files under `runtime/manual_production`, `runtime/submission_pack`, `runtime/final_submission_v47_5`, and `runtime/tender_submission_pipeline`
- inferring proof/submission success from generated files alone

Folder presence is acceptable for artifact storage but not as the primary state machine.

## JSON-Driven State
These JSON files are currently acting as mutable databases:

- `runtime/rfq_lifecycle/rfqs.json`
- `runtime/live_rfqs.json`
- `runtime/system_state/system_state.json`
- `runtime/submission_history/submission_history.json`
- `runtime/auth/users.json`
- `data/crawl_cycle_state.json`

These are the highest-priority candidates to move behind PostgreSQL-backed canonical records.

## Temporary Runtime Artifacts
The following should remain non-canonical:

- `runtime/tmp_*`
- E2E fixture JSON under `runtime/e2e_fixtures`
- pricing summaries and simulation outputs
- fetch failure snapshots
- browser/session state such as `runtime/playwright_profiles`, `runtime/chrome-profile`
- `runtime/celerybeat-schedule.db`

## Unsafe Persistence Patterns

- mutable JSON files written by multiple processes without transactional locking
- duplicate truth between PostgreSQL, SQLite, and JSON
- state inferred from file existence rather than explicit status rows
- using Redis/Celery result state as workflow truth
- local SQLite stores inside a production runtime intended to use PostgreSQL
- silent recreation of corrupt JSON stores, which may discard operational history

## Runtime Persistence Strategy

### Canonical strategy

1. PostgreSQL stores mutable business and workflow state.
2. Redis stores only queue transport and ephemeral worker results.
3. Filesystem stores binary artifacts, exports, proofs, and caches.
4. Immutable audit records are stored append-only in PostgreSQL, with file references and checksums for large evidence payloads.

### Transitional strategy

- Keep existing JSON/SQLite writers alive during migration.
- Treat them as compatibility layers or derived projections.
- Add reconciliation rules: database wins when JSON and DB disagree.
- Move API read paths off `runtime/*.json` before removing file writers.

## Recommendations

### What should remain file-based

- downloaded source files
- generated quote/submission documents
- screenshots and browser proofs
- exports, reports, and large debug payloads
- browser profiles and temporary automation sessions

### What must become database state

- tender identity and lifecycle
- document metadata and processing status
- BOQ extraction status and normalized outputs
- pricing and commercial approval status
- adjudication decisions
- submission attempts, outcomes, and retries
- worker execution records
- system control state
- operator identity and access records

### What should become immutable audit records

- every lifecycle transition
- manual overrides and approval decisions
- pricing approval and rejection rationale
- submission dispatch attempts and proof capture
- governance lock/unlock decisions

## Migrations and Schema Position

- No Alembic or migration directory was found during this audit.
- Current DB bootstrap is `Base.metadata.create_all(...)` in [app/main.py](/Users/cash/Documents/app/main.py) and [app/db/session.py](/Users/cash/Documents/app/db/session.py).
- Production already expects PostgreSQL, but state ownership is not yet consolidated there.

## Decision
PostgreSQL should be the canonical source of truth for LMCP runtime state. JSON and SQLite stores should be reduced to one of three roles only:

- derived read models
- immutable evidence artifacts
- temporary caches

They should no longer be the mutable master state for tenders, documents, pricing, submissions, or workers.
