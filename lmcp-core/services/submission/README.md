# Submission Service

`lmcp-core/services/submission/` is the target home for submission package assembly, controlled portal-delivery workflows, proof capture, and submission retry orchestration.

## Ownership

This service boundary owns:

- portal submission automation and upload orchestration
- form autofill and browser upload workflows
- submission pack generation and release preparation
- proof generation, receipt capture, and submission history
- scheduler-triggered submission loops and retry handling
- final submission lifecycle progression
- portal credential/runtime handling and submission validation gates

## Current Runtime Sources

The active submission runtime still lives in the current backend tree. Primary source modules include:

- `app/services/submission_pipeline.py`
- `app/services/tender_submission_pipeline.py`
- `app/services/submission_execution_service.py`
- `app/services/submission_engine.py`
- `app/services/portal_submission_service.py`
- `app/services/portal_submission_v47_service.py`
- `app/services/portal_upload_service.py`
- `app/services/portal_form_autofill_v47_1_service.py`
- `app/services/submission_pack_assembler_service.py`
- `app/services/submission_pack_v45_service.py`
- `app/services/submission_proof_service.py`
- `app/services/proof_of_submission_service.py`
- `app/services/submission_retry_service.py`
- `app/services/governed_submission_service.py`

## Migration Posture

This controlled migration does not move any live Python submission module. It establishes the `lmcp-core` landing zone and centralizes migration documentation while preserving:

- `app.main:app` as the official backend entrypoint
- current router registration
- current proof and retry queue behavior
- current controlled-submission safety posture
- current runtime proof, portal, and submission artifact paths

## Subdirectories

- `docs/`
  - submission source maps and migration references
- `runtime/`
  - future home for submission-owned proof, portal, and delivery artifacts after compatibility work is complete
- `configs/`
  - future home for submission-owned static portal and release configuration once it can be separated safely

## Out of Scope

This boundary does not yet absorb:

- upstream acquisition or intelligence logic
- commercial pricing ownership
- frontend assets
- governance policy authority, even where governance services currently gate submission behavior
