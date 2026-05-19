# Service Layer Baseline

## Purpose

This branch establishes a production-safe service baseline for LMCP AutoQuote.

The goal is consolidation and standardization, not new business behavior.

## Production-Safe Services

The current safe baseline centers on the services that already support manual production and controlled workflow progression:

- `manual_approval_service`
- `submission_review_service`
- `submission_proof_service`
- `workflow_state_engine`
- `audit_trail_service`
- `pilot_run_log_service`
- `pricing_engine`
- `real_profit_pricing_service`
- `quote_pack_service`
- `quote_pack_builder_service`
- `quote_engine_service`
- `quote_compilation_service`
- `auto_quote_trigger_engine`
- `submission_pipeline`
- `tender_pipeline`
- `rfq_lifecycle_service`

## Legacy Service Policy

Legacy and versioned services are retained for compatibility until a safe migration path exists.

They are explicitly tagged with `LEGACY_SERVICE = True` or classified as non-production in the service registry.

Do not delete these services without first providing a compatibility path.

## Workflow Integration Rules

- Workflow stages must be coordinated through `app.core.workflow_state_engine`.
- `review_ready` must not appear without `approved`.
- `proof_recorded` must not appear without `review_ready`.
- No service should create a parallel workflow state store.
- Manual-production services may continue writing their existing JSONL logs, but workflow transitions must be recorded centrally when valid.

## Runtime Integration Rules

- Runtime directories must come from `app.core.runtime_paths`.
- Environment setup should be centralized through `app.core.runtime_config`.
- Services should not hardcode new runtime roots or reimplement manual-production directory creation.

## Schema Integration Rules

- Prefer the typed domain layer for submission, workflow, audit, and pricing payloads.
- Use:
  - `RFQRecord`
  - `PricingDecision`
  - `QuotePack`
  - `ApprovalRecord`
  - `SubmissionReview`
  - `SubmissionProof`
  - `WorkflowState`
- Keep dict payloads compatible during migration, but reduce ad hoc field drift where safe.

## Deprecation Guidance

- Mark duplicated or obsolete implementations clearly.
- Keep deprecated services callable until a compatibility path is proven.
- Prefer deprecation plus consolidation over deletion.

## No Parallel Service Systems

The repository should maintain one canonical workflow state engine, one canonical runtime path layer, and one canonical service registry for classification.

Do not add parallel service systems that bypass these layers.
