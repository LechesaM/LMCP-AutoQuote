# Submission Migration Report

Date: 2026-06-22
Scope: first controlled submission extraction into `lmcp-core/services/submission/`

## Objective

Create the initial `lmcp-core` submission landing zone without breaking:

- `app.main:app`
- `/health`
- `/status`
- current proof and retry queue behavior
- current controlled-submission safety posture
- existing imports and API routes

## Submission Source Assets

The current submission surface includes:

- portal submission automation and browser upload workflows
- form autofill and portal interaction helpers
- submission pack generation and packaging
- proof generation, receipt capture, and proof indexing
- submission scheduling, retry handling, and reconciliation
- final submission lifecycle progression and validation gates
- go-live guardrails and production lock enforcement

Primary live source modules:

- `app/services/submission_pipeline.py`
- `app/services/tender_submission_pipeline.py`
- `app/services/submission_execution_service.py`
- `app/services/submission_engine.py`
- `app/services/portal_submission_service.py`
- `app/services/portal_submission_v47_service.py`
- `app/services/portal_upload_service.py`
- `app/services/portal_form_autofill_v47_1_service.py`
- `app/services/submission_pack_assembler_service.py`
- `app/services/submission_proof_service.py`
- `app/services/proof_of_submission_service.py`
- `app/services/submission_retry_service.py`
- `app/services/governed_submission_service.py`

## Active Submission Entrypoints

Active task and lifecycle entrypoints:

- `app.tasks.rfq_lifecycle_proof_task`
- `app.tasks.rfq_lifecycle_retry_task`
- `app.tasks.submission_scheduler_tasks.run_autonomous_submission_loop_task`
- `app.services.rfq_lifecycle_service.RfqLifecycleService.run_controlled_submission`

Active API entrypoints:

- `app/api/portal_submission_api.py`
- `app/api/portal_submission_v47_api.py`
- `app/api/portal_form_autofill_v47_1_api.py`
- `app/api/smart_upload_v47_4_api.py`
- `app/api/proof_center_api.py`
- `app/api/proof_of_submission_api.py`
- `app/api/submission_pipeline_api.py`
- `app/api/submission_retry_api.py`
- `app/api/submission_scheduler_api.py`
- `app/api/submission_history.py`

## Celery Ownership

Current queue ownership is shared with the lifecycle runtime:

- `proof_queue`
  - exposed by `app.tasks.rfq_lifecycle_proof_task`
  - actual proof progression runs inside `RfqLifecycleService.run_controlled_submission`
- `retry_queue`
  - exposed by `app.tasks.rfq_lifecycle_retry_task`
  - receives failed, blocked, and review-routed cases through lifecycle orchestration
- submission scheduler task
  - `app.tasks.submission_scheduler_tasks.run_autonomous_submission_loop_task`
  - wraps `run_autonomous_submission_loop()` with retry/backoff behavior

Submission is therefore not yet an isolated worker boundary. Queue ownership is logical, but execution still flows through shared lifecycle and governance controls.

## Browser and Runtime Dependencies

The current submission runtime depends on browser and automation surfaces including:

- Playwright/browser-based portal automation helpers
- persistent portal session state and upload workspaces
- portal autofill and upload orchestration services
- proof and receipt generation artifacts written to runtime directories

## Filesystem and Runtime Dependencies

The current submission surface depends directly on:

- `runtime/portal_submission/`
- `runtime/portal_uploads/`
- `runtime/submission_pack/`
- `runtime/submission_packages/`
- `runtime/submission_proofs/`
- `runtime/submission_history/`
- `runtime/submission_scheduler/`
- `runtime/proof_center/`
- `runtime/final_submission_v47_5/`
- `runtime/final_tender_submission/`
- `runtime/rfq_lifecycle/proofs/`
- `runtime/manual_production/governed_submissions/`
- `runtime/manual_production/submission_executions/`
- `runtime/manual_production/submission_packages/`
- `runtime/manual_production/submission_proofs.jsonl`
- `runtime/locks/immutable_submission/`
- `runtime/production_lock/`

## Portal Automation Dependencies

Submission currently depends on:

- buyer portal web interfaces
- portal-specific form autofill logic
- upload sequencing and receipt/confirmation capture
- portal credentials and session/runtime handling managed outside a single isolated boundary

## Submission State Ownership

Submission state is currently split across:

- RFQ lifecycle item fields such as `submission_status`, `proof_path`, `proof_manifest`, `proof_timestamp`, `submission_attempt_log`, and `submission_safety`
- submission history JSON artifacts under `runtime/submission_history/`
- proof manifests and receipt artifacts under `runtime/*proof*`
- relational `submission_records` linked from `quote_drafts` in `app/models/core.py`

This is not yet a single canonical submission state model.

## Proof and Audit Ownership

Proof and audit ownership is also split:

- controlled proof manifests are produced from `rfq_lifecycle_service`
- proof-center and proof-of-submission services maintain their own runtime artifacts
- manual-production JSONL files record governed submissions, proofs, and review actions
- governance-owned audit and lock services still participate in submission safety decisions

## Irreversible-Operation Risks

Submission is the most sensitive operational boundary because it can create irreversible external actions.

Key risks:

- final portal submit actions can send irrevocable buyer-facing submissions
- upload and proof flows can create misleading state if proof is captured without authoritative external confirmation
- retry automation can repeat externally sensitive steps if state ownership is unclear
- portal credentials and session reuse create operational and compliance risk

## Coupling Risks

The main coupling risks that still block direct source relocation are:

- submission progression is orchestrated inside `rfq_lifecycle_service`
- proof generation, lifecycle transitions, and safety policy are not isolated from each other
- go-live guards, production locks, and immutable submission locks remain interwoven with runtime submission decisions
- submission pack generation overlaps with commercial artifacts and downstream proof generation
- retry supervision overlaps with both governance and submission execution

## Unsafe Shared State

The current unsafe shared-state patterns include:

- runtime JSON and folder artifacts used as mutable submission state
- proof manifests and attempt logs living alongside lifecycle item fields
- duplicate persistence across SQLAlchemy tables, JSON artifacts, and runtime lock/policy files
- manual-production files acting as operational state outside a canonical database boundary

## External-System Dependencies

The current submission surface depends on:

- buyer portals and web flows
- browser automation runtime and session handling
- email-based submission paths where applicable
- operator approval and policy controls before real external execution

## Human Review and Approval Classification

Operations that must remain human-reviewed:

- final buyer-facing submission decisions
- portal actions that would execute a real irreversible submit
- overrides of validation, lock, or go-live policy failures

Operations currently safe for autonomous execution:

- controlled proof-package generation
- simulated submission-readiness progression that does not upload or submit
- retry classification and queueing where no external side effect occurs

Operations requiring approval gates:

- any transition that would lift `final_autonomous_submission_locked`
- portal upload or final submit under production conditions
- governed release decisions blocked by go-live guard or production lock

## Current Safety Posture

The current runtime still hard-blocks final autonomous submission in the lifecycle path.

Observed safeguards include:

- `requires_human_approval: true`
- `final_autonomous_submission_locked: true`
- controlled submission modes with `portal_upload_executed: false`
- explicit `no_portal_upload` and `no_final_submit` safety markers during controlled proof generation

## Future Extraction Order

Recommended submission extraction order:

1. Extract submission-owned documentation and static config contracts first.
2. Extract read-only proof and submission-history adapters behind compatibility wrappers.
3. Extract runtime path adapters for proof, portal, and submission-pack artifacts.
4. Extract scheduler and retry helpers after external side-effect boundaries are explicit.
5. Extract live portal automation, governed release logic, and lifecycle-facing submission orchestration last.

Modules that should wait:

- `app/services/portal_submission_service.py`
- `app/services/submission_execution_service.py`
- `app/services/submission_retry_service.py`
- `app/services/governed_submission_service.py`
- `app/services/rfq_lifecycle_service.py`
- `app/services/go_live_guard_service.py`

## What Was Migrated

The migration was intentionally limited to submission-owned documentation and target scaffolding:

- updated `lmcp-core/services/submission/README.md`
- created `lmcp-core/services/submission/docs/SOURCE_MAP.md`
- created `lmcp-core/services/submission/runtime/README.md`
- created `lmcp-core/services/submission/configs/README.md`

This establishes the `lmcp-core` target boundary for submission without changing runtime behavior.

## Rollback Instructions

This migration is documentation-only and can be rolled back without runtime impact by removing:

- `lmcp-core/services/submission/docs/SOURCE_MAP.md`
- `lmcp-core/services/submission/runtime/README.md`
- `lmcp-core/services/submission/configs/README.md`
- the updated content in `lmcp-core/services/submission/README.md`
- `docs/SUBMISSION_MIGRATION_REPORT.md`

No backend imports, API routes, task registration, runtime files, or compose files were changed in this step.
