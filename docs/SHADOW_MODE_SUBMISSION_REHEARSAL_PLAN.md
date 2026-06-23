# Shadow-Mode Submission Rehearsal Plan

## Purpose
Define a controlled shadow-mode submission rehearsal framework for staging validation. This plan is documentation only and does not enable live submissions, remove submission locks, or trigger irreversible actions.

## Simulated submission preparation flow
1. Select a staging RFQ that is already prepared to the point where submission packaging would normally be possible.
2. Verify the RFQ remains locked by the existing submission-lock and go-live guard surfaces.
3. Build the submission-ready artifact set in dry-run mode only.
4. Record the simulated submission candidate, approval context, and proof references.
5. Stop before any portal execution or live credential use.

## Simulated approval flow
1. Operator reviews the RFQ package, dry-run summary, and guard summary.
2. Operator confirms the artifact set is complete enough for rehearsal.
3. Operator approves the rehearsal only as a shadow exercise, not as a live submission.
4. The rehearsal records the approval decision and retains it as an audit artifact.

## Simulated proof generation
1. Generate proof artifacts from the rehearsal package.
2. Record the proof path, proof manifest, and any receipt-like evidence generated in dry-run mode.
3. Mark all proof outputs as simulated and non-submittable.
4. Retain proof artifacts for operator review and later audit comparison.

## Simulated upload validation
1. Validate the upload package structure and file naming.
2. Confirm the rehearsal package is upload-ready in form only.
3. Verify that no live portal upload is performed.
4. Verify that no live credential is required or consumed.

## Operator review checkpoints
- After dry-run package preparation.
- After simulated approval.
- After simulated proof generation.
- After simulated upload validation.
- Before any step that would normally precede a portal upload.

## Submission lock verification
- Confirm the submission lock exists for the RFQ or quote under rehearsal.
- Confirm the go-live guard remains in a blocked or guarded state.
- Confirm the rehearsal does not clear or bypass the submission lock.
- Confirm the lock state is visible in telemetry and audit outputs.

## Rollback and recovery expectations
- If the rehearsal exposes an ambiguous state, stop and revert to the last safe dry-run state.
- Preserve proof, audit, and guard evidence during rollback.
- Do not auto-retry into a live submission path.
- Recovery should restore visibility, not execution, if a rehearsal step fails.

## Expected telemetry events
- `shadow_rehearsal_started`
- `shadow_rehearsal_package_prepared`
- `shadow_rehearsal_approval_recorded`
- `shadow_rehearsal_proof_generated`
- `shadow_rehearsal_upload_validated`
- `shadow_rehearsal_blocked`
- `shadow_rehearsal_completed`

## Expected state transitions
- Dry-run ready to shadow rehearsal candidate.
- Shadow rehearsal candidate to simulated approval held.
- Simulated approval held to proof-captured.
- Proof-captured to upload-validated.
- No transition to live submitted or externally submitted states.

## Expected audit artifacts
- Rehearsal start record.
- Package preparation record.
- Operator approval record.
- Simulated proof record.
- Simulated upload validation record.
- Blocked-action record where appropriate.

## Expected queue behavior
- No live submission queue entry should be created.
- Any rehearsal task should remain in a dry-run or simulated lane.
- Retry traffic, if any, must remain within the rehearsal sandbox.
- Dead-letter handling should remain observational only.

## Expected worker behavior
- Workers may process rehearsal packaging, proof, and validation tasks.
- Workers must not execute live portal upload or final submission.
- Worker heartbeats should continue normally during rehearsal.
- Any worker deviation should surface as an operator warning, not an automatic release to live execution.

## Explicit irreversible-action protections
- Live portal submission is prohibited.
- Live credentials are prohibited.
- Submission-lock removal is prohibited during rehearsal.
- Any action that would cause an irreversible external side effect must remain blocked.

## Portal isolation enforcement
- Rehearsal must run against isolated staging or sandbox portal targets only.
- Browser automation must not reach production endpoints.
- Any portal action must fail closed if isolation cannot be confirmed.

## Dry-run-only guarantees
- The rehearsal is a shadow exercise only.
- The workflow may simulate submission readiness but may not submit.
- All outputs must clearly indicate simulation status.
- No production queue, database, or credential path may be used.

## Recommended rehearsal cadence
- Start with manual, infrequent rehearsals.
- Increase cadence only after telemetry, operator review, and rollback behavior remain stable.
- Avoid concurrent rehearsals until lock, proof, and queue visibility are proven reliable.

## Recommended operator workflow
- One operator prepares the rehearsal.
- A second operator reviews the simulated approval and proof outputs when possible.
- The operator responsible for the rehearsal must confirm blocking evidence before proceeding to the next checkpoint.

## Recommended escalation procedure
- Escalate if any lock is missing, any portal isolation check fails, or any simulated step exposes live-submission risk.
- Escalate if telemetry becomes stale or ambiguous.
- Escalate if a rehearsal step cannot be clearly classified as dry-run or shadow-only.
- Stop the rehearsal immediately and preserve evidence before retrying.

## Constraint
This document is documentation only. It does not modify orchestration, queue topology, runtime behavior, or submission authority.
