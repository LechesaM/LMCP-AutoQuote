# Submission Source Map

This source map identifies the current runtime assets that belong logically to the Submission Service boundary.

## Primary Submission and Portal Modules

- `app/services/submission_pipeline.py`
- `app/services/tender_submission_pipeline.py`
- `app/services/submission_execution_service.py`
- `app/services/submission_engine.py`
- `app/services/portal_submission_service.py`
- `app/services/portal_submission_v47_service.py`
- `app/services/portal_upload_service.py`
- `app/services/smart_upload_v47_4_service.py`
- `app/services/upload_dry_run_service.py`
- `app/services/portal_form_autofill_v47_1_service.py`

## Submission Pack and Proof Modules

- `app/services/submission_pack_assembler_service.py`
- `app/services/submission_pack_v45_service.py`
- `app/services/submission_package_service.py`
- `app/services/proof_center_service.py`
- `app/services/proof_of_submission_service.py`
- `app/services/submission_proof_service.py`
- `app/services/submission_proof_artifact_service.py`
- `app/services/submission_receipt_verification_service.py`
- `app/services/auto_proof_after_submission_service.py`
- `app/services/auto_proof_after_submission_v2.py`

## Scheduling, Retry, and History

- `app/services/submission_scheduler_service.py`
- `app/services/autonomous_submission_loop_service.py`
- `app/services/submission_retry_service.py`
- `app/services/retry_engine_service.py`
- `app/services/submission_history_service.py`
- `app/services/submission_history_recent_service.py`
- `app/services/submission_history_pipeline_sync_service.py`
- `app/services/submission_history_proof_enrichment_service.py`
- `app/services/submission_reconciliation_service.py`

## Governance-Coupled Submission Controls

- `app/services/go_live_guard_service.py`
- `app/services/governed_submission_service.py`
- `app/services/production_lock_service.py`
- `app/services/immutable_submission_lock_service.py`
- `app/services/security_guard_service.py`
- `app/services/submission_quality_service.py`
- `app/services/submission_review_service.py`
- `app/services/submission_verification_v47_6_service.py`

## Active Submission Entrypoints

Active task and lifecycle entrypoints currently include:

- `app.tasks.rfq_lifecycle_proof_task`
- `app.tasks.rfq_lifecycle_retry_task`
- `app.tasks.submission_scheduler_tasks.run_autonomous_submission_loop_task`
- `app.services.rfq_lifecycle_service.RfqLifecycleService.run_controlled_submission`

Active API surfaces that expose or trigger submission behavior include:

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

## Runtime and Filesystem Dependencies

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

## Not Migrated In This Step

These runtime-owned APIs and Python modules remain in place and are not moved in this first submission extraction step.
