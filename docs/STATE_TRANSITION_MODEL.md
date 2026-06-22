# LMCP State Transition Model

## Purpose
This document defines the canonical state transition model LMCP should follow once PostgreSQL becomes the source of truth for runtime workflow state. It is a documentation-only target model based on the current lifecycle and queue behavior in [app/services/rfq_lifecycle_service.py](/Users/cash/Documents/app/services/rfq_lifecycle_service.py), [app/celery_app.py](/Users/cash/Documents/app/celery_app.py), and the existing runtime JSON stores.

## Principles

- one canonical tender workflow per RFQ/tender
- explicit state transitions, never inferred solely from file presence
- retries are first-class state transitions
- worker transport state is not the business truth
- every transition produces an append-only audit event

## Acquisition Lifecycle

### States

- `DISCOVERED`
- `QUALIFIED`
- `DOCUMENT_ACQUISITION_PENDING`
- `DOCUMENT_ACQUISITION_IN_PROGRESS`
- `DOCUMENT_ACQUISITION_BLOCKED`
- `BUYER_PACK_VERIFIED`
- `DOCUMENTS_ACQUIRED`
- `REVIEW_REQUIRED`
- `FAILED`
- `READY_FOR_RETRY`
- `REJECTED`

### Transition rules

- `DISCOVERED -> QUALIFIED`
  Trigger: tender passes supply-and-delivery qualification rules.
- `QUALIFIED -> DOCUMENT_ACQUISITION_PENDING`
  Trigger: tender is accepted into acquisition workflow.
- `DOCUMENT_ACQUISITION_PENDING -> DOCUMENT_ACQUISITION_IN_PROGRESS`
  Trigger: worker claims acquisition job.
- `DOCUMENT_ACQUISITION_IN_PROGRESS -> BUYER_PACK_VERIFIED`
  Trigger: buyer pack is downloaded and minimum metadata is validated.
- `BUYER_PACK_VERIFIED -> DOCUMENTS_ACQUIRED`
  Trigger: acquired pack and document inventory are committed.
- `DOCUMENT_ACQUISITION_IN_PROGRESS -> DOCUMENT_ACQUISITION_BLOCKED`
  Trigger: site access, credential, anti-bot, or missing-link blocker.
- `DOCUMENT_ACQUISITION_IN_PROGRESS -> FAILED`
  Trigger: terminal acquisition error.
- `DOCUMENT_ACQUISITION_BLOCKED -> READY_FOR_RETRY`
  Trigger: recovery policy says retry is safe.
- `FAILED -> READY_FOR_RETRY`
  Trigger: failure classified as retryable.
- any non-terminal state -> `REJECTED`
  Trigger: out-of-policy tender, closing date passed, duplicate, or governance exclusion.

## Extraction Lifecycle

This covers document classification, BOQ detection, pricing schedule detection, and SBD/returnables interpretation.

### States

- `DOCUMENTS_ACQUIRED`
- `DOCUMENTS_CLASSIFYING`
- `DOCUMENTS_PARSED`
- `BOQ_CANDIDATE`
- `BOQ_EXTRACTING`
- `BOQ_EXTRACTED`
- `BOQ_VERIFIED`
- `QUANTITY_VERIFICATION_REQUIRED`
- `COMMERCIAL_VERIFICATION_REQUIRED`
- `REVIEW_REQUIRED`
- `FAILED`
- `READY_FOR_RETRY`

### Transition rules

- `DOCUMENTS_ACQUIRED -> DOCUMENTS_CLASSIFYING`
  Trigger: parsing worker claims document analysis job.
- `DOCUMENTS_CLASSIFYING -> DOCUMENTS_PARSED`
  Trigger: classification and parse summary are committed.
- `DOCUMENTS_PARSED -> BOQ_CANDIDATE`
  Trigger: one or more documents are classified as BOQ candidates.
- `BOQ_CANDIDATE -> BOQ_EXTRACTING`
  Trigger: BOQ extraction job starts.
- `BOQ_EXTRACTING -> BOQ_EXTRACTED`
  Trigger: rows are extracted with machine-readable output.
- `BOQ_EXTRACTED -> BOQ_VERIFIED`
  Trigger: normalization and quality checks pass.
- `BOQ_EXTRACTED -> QUANTITY_VERIFICATION_REQUIRED`
  Trigger: extraction exists but quantity/unit integrity is uncertain.
- `DOCUMENTS_PARSED -> COMMERCIAL_VERIFICATION_REQUIRED`
  Trigger: pricing schedule or returnables are incomplete or ambiguous.
- extraction states -> `REVIEW_REQUIRED`
  Trigger: manual review required but not yet failed.
- extraction states -> `FAILED`
  Trigger: parse/extraction process is not recoverable without operator or requeue.
- `FAILED` or `REVIEW_REQUIRED` -> `READY_FOR_RETRY`
  Trigger: corrected input or retry policy permits another attempt.

## Pricing Lifecycle

### States

- `BOQ_VERIFIED`
- `PRICING_PENDING`
- `PRICING_IN_PROGRESS`
- `PRICED`
- `PRICING_VERIFIED`
- `APPROVAL_READY`
- `COMMERCIAL_VERIFICATION_REQUIRED`
- `REVIEW_REQUIRED`
- `FAILED`
- `READY_FOR_RETRY`

### Transition rules

- `BOQ_VERIFIED -> PRICING_PENDING`
  Trigger: extraction is complete enough for pricing.
- `PRICING_PENDING -> PRICING_IN_PROGRESS`
  Trigger: pricing worker claims job.
- `PRICING_IN_PROGRESS -> PRICED`
  Trigger: totals, margin, and supplier selections are generated.
- `PRICED -> PRICING_VERIFIED`
  Trigger: automated pricing validation passes.
- `PRICING_VERIFIED -> APPROVAL_READY`
  Trigger: commercial pack is complete and governance gates pass.
- `PRICING_IN_PROGRESS -> COMMERCIAL_VERIFICATION_REQUIRED`
  Trigger: low confidence, missing rates, or pricing schedule mismatch.
- `PRICING_IN_PROGRESS -> REVIEW_REQUIRED`
  Trigger: operator review required.
- `PRICING_IN_PROGRESS -> FAILED`
  Trigger: pricing engine failure or unrecoverable source problem.
- `FAILED` or `REVIEW_REQUIRED` -> `READY_FOR_RETRY`
  Trigger: retry policy allows re-run.

## Submission Lifecycle

### States

- `QUOTE_PACK_READY`
- `APPROVAL_READY`
- `SUBMISSION_READY_MANUAL`
- `SUBMISSION_READY`
- `DISPATCHING`
- `EXTERNALLY_SUBMITTED`
- `SUBMITTED`
- `PROOF_CAPTURED`
- `ARCHIVED`
- `MANUAL_INTERVENTION_REQUIRED`
- `FAILED`
- `READY_FOR_RETRY`

### Transition rules

- `APPROVAL_READY -> SUBMISSION_READY_MANUAL`
  Trigger: workflow requires human approval or supervised release.
- `APPROVAL_READY -> SUBMISSION_READY`
  Trigger: all release controls are satisfied for dispatch.
- `SUBMISSION_READY` or `SUBMISSION_READY_MANUAL` -> `DISPATCHING`
  Trigger: email/portal submission execution starts.
- `DISPATCHING -> EXTERNALLY_SUBMITTED`
  Trigger: remote system accepted the submission but proof capture is not complete.
- `EXTERNALLY_SUBMITTED -> SUBMITTED`
  Trigger: submission confirmation is committed.
- `SUBMITTED -> PROOF_CAPTURED`
  Trigger: immutable proof artifacts are captured and linked.
- `PROOF_CAPTURED -> ARCHIVED`
  Trigger: operational closure completed.
- dispatch states -> `MANUAL_INTERVENTION_REQUIRED`
  Trigger: partial submission, uncertain outcome, or portal mismatch.
- dispatch states -> `FAILED`
  Trigger: submission not completed.
- `FAILED` or `MANUAL_INTERVENTION_REQUIRED` -> `READY_FOR_RETRY`
  Trigger: retry policy and tender timing permit another attempt.

## Worker Execution Lifecycle

Worker lifecycle is separate from tender lifecycle. Celery remains execution transport.

### States

- `PENDING`
- `RUNNING`
- `COMPLETED`
- `FAILED`
- `RETRY_PENDING`
- `BLOCKED`
- `DEAD_LETTERED`
- `CANCELLED`

### Rules

- every business-stage transition may spawn one or more worker executions
- worker completion may advance the tender lifecycle
- worker failure does not automatically equal tender failure
- terminal worker state must persist failure class, attempt count, and next action

## Failure and Retry Model

### Retryable failures

- temporary network failure
- transient broker/worker interruption
- recoverable extraction failure
- transient DB lock/connectivity failure
- external portal timeout

Canonical result:

- business entity enters `READY_FOR_RETRY`
- worker execution enters `RETRY_PENDING`
- retry metadata records `attempt_count`, `last_error`, `next_retry_at`, and `retry_policy`

### Non-retryable failures

- tender closed
- policy rejection
- irreparable source corruption
- missing mandatory documents with no recovery path
- governance rejection

Canonical result:

- business entity enters `FAILED` or `REJECTED`
- no automatic requeue

## Dead-Letter Concept

There is no explicit dead-letter queue configuration in the current Celery setup. A logical dead-letter concept is still relevant.

### Recommended logical model

- `DEAD_LETTERED` worker state
- `dead_letter_reason`
- `dead_lettered_at`
- `original_queue`
- `original_stage`
- `attempt_count`

### When to dead-letter

- max retries exceeded
- repeated deterministic failure
- malformed payload that cannot be safely retried
- workflow version mismatch

### Operational meaning

- dead-lettered work is not lost
- it is removed from automatic retry circulation
- it requires explicit operator or recovery workflow action

## Ownership Mapping

### PostgreSQL canonical records should own

- current tender state
- state transition history
- document processing state
- pricing/adjudication/submission state
- worker execution state
- retry and dead-letter metadata

### Filesystem should own

- downloaded documents
- generated quote packs
- submission proofs
- screenshots
- large reports and exports

### Redis/Celery should own

- queue transport
- in-flight task messaging
- short-lived execution result cache only

## Current Gaps

- state is split across PostgreSQL-capable tables, JSON files, and SQLite files
- `runtime/rfq_lifecycle/rfqs.json` acts as the current workflow master
- `runtime/live_rfqs.json` acts as a read model but is also used operationally
- submission truth is duplicated across DB tables and JSON histories
- no visible migration framework exists yet
- no explicit dead-letter persistence model exists yet

## Transitional Rule
Until schema work starts, the safest interpretation is:

- PostgreSQL is the intended canonical destination.
- JSON and SQLite stores are still active compatibility stores.
- New stabilization work should prefer modeling transitions as database-owned concepts even if temporary file projections remain in place.
