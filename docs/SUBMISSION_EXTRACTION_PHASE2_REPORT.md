# Submission Extraction Phase 2 Report

Date: 2026-06-22
Scope: controlled submission extraction review for `lmcp-core/services/submission/`

## Decision

No submission module was moved in this phase.

After review, I did not find a submission utility that was both:

- isolated enough to relocate safely
- free of browser execution, upload side effects, or workflow orchestration coupling
- safe to preserve through compatibility shims without changing runtime behavior

## What Was Reviewed

The following submission-related runtime modules were inspected as potential low-risk candidates:

- `app/services/submission_pack_assembler_service.py`
- `app/services/submission_proof_service.py`
- `app/services/proof_of_submission_service.py`
- `app/services/submission_retry_service.py`
- `app/services/governed_submission_service.py`
- `app/services/submission_execution_service.py`
- `app/services/submission_quality_service.py`
- `app/services/submission_receipt_verification_service.py`
- `app/services/submission_package_service.py`
- `app/services/submission_history_service.py`
- `app/services/submission_proof_artifact_service.py`

## Why Nothing Was Moved

The reviewed modules are still coupled to active submission workflow state, file-system side effects, or approval/retry orchestration.

Examples of coupling that blocked extraction:

- submission proof helpers write runtime proof logs and persist records
- submission pack helpers depend on live RFQ payloads and runtime artifact paths
- receipt and execution helpers read and write execution state, idempotency state, and proof artifacts
- retry helpers invoke active email and portal submission flows
- governed submission helpers create approval-chain, lock, and audit state as part of the submission lifecycle
- validation and quality helpers depend on pricing, review readiness, and submission-package state

## Compatibility Shims

No compatibility shims were added because no live submission module was relocated.

## Remaining Risks

The submission boundary still has the same tight coupling risks identified in the service-boundary documentation:

- browser automation and portal upload code are still embedded in the active backend tree
- proof generation, execution, and history persistence remain mixed with workflow orchestration
- submission retry and governed submission logic still own runtime state transitions
- filesystem artifacts under `runtime/manual_production/`, `runtime/submission_*`, and related proof folders remain part of the live execution path

## Future Extraction Order

The safest future order remains:

1. pure metadata or naming helpers, if they can be isolated from workflow state
2. read-only reporting helpers
3. proof/history formatting helpers with no write path
4. submission packaging helpers only after their file-system dependencies are detached
5. execution, retry, and governed submission modules last

## Rollback Instructions

Because nothing was moved, rollback is not required.

If a future submission extraction is later introduced, rollback should restore:

- the original `app/services/*` implementation files
- any compatibility shims added at the original import paths
- any documentation added for that extraction step

## Conclusion

Submission Phase 2 is currently blocked by workflow coupling. The correct stabilization action is to leave the current runtime unchanged until a genuinely isolated utility appears.
